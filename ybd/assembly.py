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
        if 'tried' not in component:
            log(component, 'No cache_key, so skipping compose')
            component['tried'] = True
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

    # Create composite components (strata, systems, clusters)
    systems = component.get('systems', [])
    shuffle(systems)
    for system in systems:
        compose(defs, system['path'])
        for subsystem in system.get('subsystems', []):
            compose(defs, subsystem)

    with sandbox.setup(component):
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
        dn = defs.get(it)
        if os.path.exists(os.path.join(component['sandbox'],
                                       'baserock', dn['name'] + '.meta')):
            # content has already been installed
            log(component, 'Already installed', dn['name'], verbose=True)
            continue

        if component.get('kind', 'chunk') == 'system':
            artifacts = []
            for content in component['contents']:
                if content.keys()[0] == dn['path']:
                    artifacts = content[dn['path']]
                    break

            if artifacts != [] or config.get('default-splits', []) != []:
                compose(defs, dn)
                install_split_artifacts(defs, component, dn, artifacts)
                continue

        for i in dn.get('contents', []):
            install_contents(defs, component, [i])

        if dn.get('build-mode', 'staging') != 'bootstrap':
            if not get_cache(defs, dn):
                compose(defs, dn)
            sandbox.install(defs, component, dn)

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


def run_build(defs, dn):
    ''' This is where we run ./configure, make, make install (for example).
    By the time we get here, all dependencies for component have already
    been assembled.
    '''

    if config.get('mode', 'normal') == 'no-build':
        log(dn, 'SKIPPING BUILD: artifact will be empty')
        return

    if dn.get('build-mode') != 'bootstrap':
        sandbox.ldconfig(dn)

    if dn.get('repo'):
        repos.checkout(dn)
        dn['SOURCE_DATE_EPOCH'] = repos.source_date_epoch(dn['build'])

    get_build_commands(defs, dn)
    env_vars = sandbox.env_vars_for_build(defs, dn)

    log(dn, 'Logging build commands to %s' % dn['log'])
    for build_step in defs.defaults.build_steps:
        if dn.get(build_step):
            log(dn, 'Running', build_step)
        for command in dn.get(build_step, []):
            command = 'false' if command is False else command
            command = 'true' if command is True else command
            sandbox.run_sandboxed(dn, command, env=env_vars,
                                  allow_parallel=('build' in build_step))
    if dn.get('devices'):
        sandbox.create_devices(dn)

    with open(dn['log'], "a") as logfile:
        time_elapsed = elapsed(dn['start-time'])
        logfile.write('Elapsed_time: %s\n' % time_elapsed)
        log_riemann(dn, 'Artifact_Timer', dn['name'], time_elapsed)


def shuffle(contents):
    if config.get('instances', 1) > 1:
        random.seed(datetime.datetime.now())
        random.shuffle(contents)


@contextlib.contextmanager
def claim(defs, dn):
    with open(lockfile(defs, dn), 'a') as l:
        try:
            fcntl.flock(l, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as e:
            if e.errno in (errno.EACCES, errno.EAGAIN):
                # flock() will report EACCESS or EAGAIN when the lock fails.
                raise RetryException(defs, dn)
            else:
                log(dn, 'ERROR: surprise exception in assembly', '')
                import traceback
                traceback.print_exc()
                exit(dn, 'ERROR: sandbox debris is at', dn['sandbox'])
        try:
            yield
        finally:
            if os.path.isfile(lockfile(defs, dn)):
                os.remove(lockfile(defs, dn))


def get_build_commands(defs, dn):
    '''Get commands specified in d, plus commands implied by build-system

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

    if dn.get('kind', None) == "system":
        # Systems must run their integration scripts as install commands
        dn['install-commands'] = gather_integration_commands(defs, dn)
        return

    bs = dn.get('build-system', 'manual')
    if dn.get('build-system', False):
        log(dn, 'Defined build system is', bs)
    else:
        if dn.get('kind', 'chunk') == 'chunk':
            if 'install-commands' not in dn:
                files = os.listdir(dn['build'])
                bs = defs.defaults.detect_build_system(files)
                if bs == 'NOT FOUND':
                    exit(dn, 'ERROR: no build-system detected,',
                         'and missing %s' % dn['path'])
        log(dn, 'WARNING: Assumed build system is', bs)

    for build_step in defs.defaults.build_steps:
        if dn.get(build_step, None) is None:
            commands = defs.defaults.build_systems[bs].get(build_step, [])
            dn[build_step] = commands


def gather_integration_commands(defs, dn):
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
    _gather_recursively(dn, all_commands)
    result = []
    for key in sorted(all_commands.keys()):
        result.extend(all_commands[key])
    return result
