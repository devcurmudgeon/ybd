# Copyright (C) 2014-2015  Codethink Limited
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

import json
import app
from cache import cache, cache_key, get_cache, get_remote
import repos
import sandbox
from shutil import copyfile
import time
import datetime


class RetryException(Exception):
    def __init__(self, defs, component):
        if app.config['log-verbose'] and \
                app.config.get('last-retry-component') != component:
            app.log(component, 'Already downloading/building, so wait/retry')
        if app.config.get('last-retry'):
            wait = datetime.datetime.now() - app.config.get('last-retry')
            if wait.seconds < 1:
                with open(lockfile(defs, component), 'r') as l:
                    call(['flock', '--shared', '--timeout',
                          app.config.get('timeout', '60'), str(l.fileno())])
        app.config['last-retry'] = datetime.datetime.now()
        app.config['last-retry-component'] = component
        for dirname in app.config['sandboxes']:
            app.remove_dir(dirname)
        app.config['sandboxes'] = []
        pass


def compose(defs, target):
    '''Work through defs tree, building and assembling until target exists'''

    component = defs.get(target)

    # if we can't calculate cache key, we can't create this component
    if cache_key(defs, component) is False:
        return False

    # if this component is already cached, we're done
    if get_cache(defs, component):
        return cache_key(defs, component)

    # if we have a kbas, look there to see if this component exists
    if app.config.get('kbas-url'):
        with claim(defs, component):
            if get_remote(defs, component):
                app.config['counter'].increment()
                return cache_key(defs, component)

    if component.get('arch') and component['arch'] != app.config['arch']:
        return None

    with sandbox.setup(component):

        assemble(defs, component)

        if 'systems' not in component and not get_cache(defs, component):
            dependencies = component.get('build-depends', [])
            for it in dependencies:
                preinstall(defs, component, it)
            build(defs, component)

    return cache_key(defs, component)


def assemble(defs, component):
    systems = component.get('systems', [])
    shuffle(systems)
    for system in systems:
        compose(defs, system['path'])
        for subsystem in system.get('subsystems', []):
            compose(defs, subsystem)

    contents = component.get('contents', [])
    shuffle(contents)
    for it in contents:
        subcomponent = defs.get(it)
        if subcomponent.get('build-mode', 'staging') != 'bootstrap':
            preinstall(defs, component, subcomponent)


def build(defs, component):
    '''Create an artifact for a single component and add it to the cache'''

    with claim(defs, component):
        app.config['counter'].increment()
        with app.timer(component, 'build of %s' % component['cache']):
            run_build(defs, component)

        with app.timer(component, 'artifact creation'):
            do_manifest(component)
            cache(defs, component)


def run_build(defs, this):
    ''' This is where we run ./configure, make, make install (for example).
    By the time we get here, all dependencies for component have already
    been assembled.
    '''

    if app.config.get('no-build'):
        app.log(this, 'SKIPPING BUILD: artifact will be empty')
        return

    if this.get('build-mode') != 'bootstrap':
        sandbox.ldconfig(this)

    if this.get('repo'):
        repos.checkout(this['name'], this['repo'], this['ref'], this['build'])

    get_build_commands(defs, this)
    env_vars = sandbox.env_vars_for_build(defs, this)

    app.log(this, 'Logging build commands to %s' % this['log'])
    for build_step in defs.defaults.build_steps:
        if this.get(build_step):
            app.log(this, 'Running', build_step)
        for command in this.get(build_step, []):
            if command is False:
                command = "false"
            elif command is True:
                command = "true"
            sandbox.run_sandboxed(
                this, command, env=env_vars,
                allow_parallel=('build' in build_step))

    if this.get('devices'):
        sandbox.create_devices(this)

    with open(this['log'], "a") as logfile:
        logfile.write('Elapsed_time: %s\n' % app.elapsed(this['start-time']))


def shuffle(contents):
    if app.config.get('instances', 1) > 1:
        random.seed(datetime.datetime.now())
        random.shuffle(contents)


def lockfile(defs, this):
    return os.path.join(app.config['tmp'], cache_key(defs, this) + '.lock')


@contextlib.contextmanager
def claim(defs, this):
    # take a lock so we don't race building 'this'
    # FIXME: we should claim always, but the claim code is eating exceptions
    # so currently we only claim on multi-instance so it's easier to debug
    # on single instance runs
    if app.config.get('instances', 1) > 1:
        try:
            with open(lockfile(defs, this), 'a') as l:
                fcntl.flock(l, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    yield
                finally:
                    return
        except IOError as e:
            raise RetryException(defs, this)
    else:
        try:
            yield
        finally:
            return


def preinstall(defs, component, it):
    '''Install it and all its recursed dependencies into component sandbox.'''
    dependency = defs.get(it)
    if os.path.exists(os.path.join(component['sandbox'], 'baserock',
                                   dependency['name'] + '.meta')):
        # dependency has already been preinstalled
        return

    dependencies = dependency.get('build-depends', [])
    for dep in dependencies:
        it = defs.get(dep)
        if (it.get('build-mode', 'staging') ==
                dependency.get('build-mode', 'staging')):
            preinstall(defs, component, it)

    contents = dependency.get('contents', [])
    shuffle(contents)
    for sub in contents:
        it = defs.get(sub)
        if it.get('build-mode', 'staging') != 'bootstrap':
            preinstall(defs, component, it)

    compose(defs, dependency)
    sandbox.install(defs, component, dependency)


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
        app.log(this, 'Defined build system is', bs)
    else:
        files = os.listdir(this['build'])
        bs = defs.defaults.detect_build_system(files)
        app.log(this, 'Autodetected build system is', bs)

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


def do_manifest(this):
    metafile = os.path.join(this['baserockdir'], this['name'] + '.meta')
    with app.chdir(this['install']), open(metafile, "w") as f:
        f.write("repo: %s\nref: %s\n" % (this.get('repo'), this.get('ref')))
        f.flush()
        call(['find'], stdout=f, stderr=f)
    copyfile(metafile, os.path.join(app.config['artifacts'],
                                    this['cache'] + '.meta'))
