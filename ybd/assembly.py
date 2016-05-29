# Copyright (C) 2014-2016  Codethink Limited
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# =*= License: GPL-2 =*=

import os
import random
from subprocess import call, check_output
import contextlib
import fcntl
import errno

import json
from app import config, chdir, exit, timer, elapsed
from app import log, log_riemann, lockfile, RetryException
from cache import cache, cache_key, get_cache, get_remote
import repos
import sandbox
from shutil import copyfile
import time
import datetime
from splitting import write_metadata, install_split_artifacts


def compose(defs, target):
    '''Work through defs tree, building and assembling until target exists'''

    component = defs.get(target)

    # if we can't calculate cache key, we can't create this component
    if cache_key(defs, component) is False:
        app.log(component, 'No cache_key, so skipping compose')
        return False

    # if this component is already cached, we're done
    if get_cache(defs, component):
        return cache_key(defs, component)

    log(target, "Composing", component['name'], verbose=True)

    # if we have a kbas, look there to see if this component exists
    if config.get('kbas-url') and not config.get('reproduce'):
        with claim(defs, component):
            if get_remote(defs, component):
                config['counter'].increment()
                return cache_key(defs, component)

    # we only work with user-specified arch
    if 'arch' in component and component['arch'] != config['arch']:
        return None

    with sandbox.setup(component):
        # Create composite components (strata, systems, clusters)
        systems = component.get('systems', [])
        shuffle(systems)
        for system in systems:
            compose(defs, system['path'])
            for subsystem in system.get('subsystems', []):
                compose(defs, subsystem)

        install_contents(defs, component)
        build(defs, component)     # bring in 'build-depends', and run make

    return cache_key(defs, component)


def install_contents(defs, component, contents=None):
    ''' Install contents (recursively) into component['sandbox'] '''

    component = defs.get(component)
    if contents is None:
        contents = component.get('contents', [])

    log(component, 'Installing contents\n', contents, verbose=True)

    shuffle(contents)
    for it in contents:
        this = defs.get(it)
        if os.path.exists(os.path.join(component['sandbox'],
                                       'baserock', this['name'] + '.meta')):
            # content has already been installed
            log(component, 'Already installed', this['name'], verbose=True)
            continue

        if component.get('kind', 'chunk') == 'system':
            artifacts = []
            for content in component['contents']:
                if content.keys()[0] == this['path']:
                    artifacts = content[this['path']]
                    break

            if artifacts != [] or config.get('default-splits', []) != []:
                compose(defs, this)
                install_split_artifacts(defs, component, this, artifacts)
                continue

        for i in this.get('contents', []):
            install_contents(defs, component, [i])

        if this.get('build-mode', 'staging') != 'bootstrap':
            if not get_cache(defs, this):
                compose(defs, this)
            sandbox.install(defs, component, this)

    if config.get('log-verbose'):
        log(component, 'Added contents\n', contents)
        sandbox.list_files(component)


def install_dependencies(defs, component, dependencies=None):
    '''Install recursed dependencies of component into component's sandbox.'''

    component = defs.get(component)
    if dependencies is None:
        dependencies = component.get('build-depends', [])

    log(component, 'Installing dependencies\n', dependencies, verbose=True)
    shuffle(dependencies)
    for it in dependencies:
        dependency = defs.get(it)
        if os.path.exists(os.path.join(component['sandbox'], 'baserock',
                                       dependency['name'] + '.meta')):
            # dependency has already been installed
            log(component, 'Already did', dependency['name'], verbose=True)
            continue

        install_dependencies(defs, component,
                             dependency.get('build-depends', []))
        if (it in component['build-depends']) or \
            (dependency.get('build-mode', 'staging') ==
                component.get('build-mode', 'staging')):
            compose(defs, dependency)
            if dependency.get('contents'):
                install_dependencies(defs, component, dependency['contents'])
            sandbox.install(defs, component, dependency)
    if config.get('log-verbose'):
        sandbox.list_files(component)


def build(defs, component):
    '''Create an artifact for a single component and add it to the cache'''

    if get_cache(defs, component):
        return

    with claim(defs, component):
        if component.get('kind', 'chunk') == 'chunk':
            install_dependencies(defs, component)
        with timer(component, 'build of %s' % component['cache']):
            run_build(defs, component)

        with timer(component, 'artifact creation'):
            write_metadata(defs, component)
            cache(defs, component)


def run_build(defs, this):
    ''' This is where we run ./configure, make, make install (for example).
    By the time we get here, all dependencies for component have already
    been assembled.
    '''

    if config.get('mode', 'normal') == 'no-build':
        log(this, 'SKIPPING BUILD: artifact will be empty')
        return

    if this.get('build-mode') != 'bootstrap':
        sandbox.ldconfig(this)

    if this.get('repo'):
        repos.checkout(this)
        this['SOURCE_DATE_EPOCH'] = repos.source_date_epoch(this['build'])

    get_build_commands(defs, this)
    env_vars = sandbox.env_vars_for_build(defs, this)

    log(this, 'Logging build commands to %s' % this['log'])
    for build_step in defs.defaults.build_steps:
        if this.get(build_step):
            log(this, 'Running', build_step)
        for command in this.get(build_step, []):
            command = 'false' if command is False else command
            command = 'true' if command is True else command
            sandbox.run_sandboxed(this, command, env=env_vars,
                                  allow_parallel=('build' in build_step))
    if this.get('devices'):
        sandbox.create_devices(this)

    with open(this['log'], "a") as logfile:
        time_elapsed = elapsed(this['start-time'])
        logfile.write('Elapsed_time: %s\n' % time_elapsed)
        log_riemann(this, 'Artifact_Timer', this['name'], time_elapsed)


def shuffle(contents):
    if config.get('instances', 1) > 1:
        random.seed(datetime.datetime.now())
        random.shuffle(contents)


@contextlib.contextmanager
def claim(defs, this):
    with open(lockfile(defs, this), 'a') as l:
        try:
            fcntl.flock(l, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as e:
            if e.errno in (errno.EACCES, errno.EAGAIN):
                # flock() will report EACCESS or EAGAIN when the lock fails.
                raise RetryException(defs, this)
            else:
                log(this, 'ERROR: surprise exception in assembly', '')
                import traceback
                traceback.print_exc()
                exit(this, 'ERROR: sandbox debris is at', this['sandbox'])
        try:
            yield
        finally:
            if os.path.isfile(lockfile(defs, this)):
                os.remove(lockfile(defs, this))


def get_build_commands(defs, this):
    '''Get commands specified in 'this', plus commands implied by build-system

    The containing definition may point to another definition file (using
    the 'path' field in YBD's internal data model) that contains build
    instructions, or it may only specify a predefined build system, using
    'build-system' field.

    The definition containing build instructions can specify a predefined
    build-system and then override some or all of the command sequences it
    defines.

    If the definition file doesn't exist and no build-system is specified,
    this function will scan the contents the checked-out source repo and try
    to autodetect what build system is used.

    '''

    if this.get('kind', None) == "system":
        # Systems must run their integration scripts as install commands
        this['install-commands'] = gather_integration_commands(defs, this)
        return

    if this.get('build-system') or os.path.exists(this['path']):
        bs = this.get('build-system', 'manual')
        log(this, 'Defined build system is', bs)
    else:
        files = os.listdir(this['build'])
        bs = defs.defaults.detect_build_system(files)
        if bs == 'NOT FOUND':
            exit(this, 'ERROR: no build-system detected,',
                 'and missing %s' % this['path'])
        log(this, 'WARNING: Autodetected build system', bs)

    for build_step in defs.defaults.build_steps:
        if this.get(build_step, None) is None:
            commands = defs.defaults.build_systems[bs].get(build_step, [])
            this[build_step] = commands


def gather_integration_commands(defs, this):
    # 1. iterate all subcomponents (recursively) looking for sys-int commands
    # 2. gather them all up
    # 3. asciibetically sort them
    # 4. concat the lists

    def _gather_recursively(component, commands):
        if 'system-integration' in component:
            for product, it in component['system-integration'].iteritems():
                for name, cmdseq in it.iteritems():
                    commands["%s-%s" % (name, product)] = cmdseq
        for subcomponent in component.get('contents', []):
            _gather_recursively(defs.get(subcomponent), commands)

    all_commands = {}
    _gather_recursively(this, all_commands)
    result = []
    for key in sorted(all_commands.keys()):
        result.extend(all_commands[key])
    return result
