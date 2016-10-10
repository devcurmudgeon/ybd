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
import contextlib
import fcntl
import errno

from ybd import app, repos, sandbox
from ybd.app import config, timer, elapsed
from ybd.app import log, log_riemann, lockfile, RetryException
from ybd.cache import cache, cache_key, get_cache, get_remote
import datetime
from ybd.splitting import write_metadata, install_split_artifacts


def compose(dn):
    '''Work through defs tree, building and assembling until target exists'''

    if type(dn) is not dict:
        dn = app.defs.get(dn)

    # if we can't calculate cache key, we can't create this component
    if cache_key(dn) is False:
        if 'tried' not in dn:
            log(dn, 'No cache_key, so skipping compose')
            dn['tried'] = True
        return False

    # if dn is already cached, we're done
    if get_cache(dn):
        return cache_key(dn)

    log(dn, "Composing", dn['name'], verbose=True)

    # if we have a kbas, look there to see if this component exists
    if config.get('kbas-url') and not config.get('reproduce'):
        with claim(dn):
            if get_remote(dn):
                config['counter'].increment()
                return cache_key(dn)

    # we only work with user-specified arch
    if 'arch' in dn and dn['arch'] != config['arch']:
        return None

    # Create composite components (strata, systems, clusters)
    systems = dn.get('systems', [])
    shuffle(systems)
    for system in systems:
        for s in system.get('subsystems', []):
            subsystem = app.defs.get(s['path'])
            compose(subsystem)
        compose(system['path'])

    with sandbox.setup(dn):
        install_contents(dn)
        build(dn)     # bring in 'build-depends', and run make

    return cache_key(dn)


def install_contents(dn, contents=None):
    ''' Install contents (recursively) into dn['sandbox'] '''

    if contents is None:
        contents = dn.get('contents', [])

    log(dn, 'Installing contents\n', contents, verbose=True)

    shuffle(contents)
    for it in contents:
        item = app.defs.get(it)
        if os.path.exists(os.path.join(dn['sandbox'],
                                       'baserock', item['name'] + '.meta')):
            # content has already been installed
            log(dn, 'Already installed', item['name'], verbose=True)
            continue

        for i in item.get('contents', []):
            install_contents(dn, [i])

        if item.get('build-mode', 'staging') != 'bootstrap':
            if not get_cache(item):
                compose(item)
            sandbox.install(dn, item)

    if config.get('log-verbose'):
        log(dn, 'Added contents\n', contents)
        sandbox.list_files(dn)


def install_dependencies(dn, dependencies=None):
    '''Install recursed dependencies of dn into dn's sandbox.'''

    if dependencies is None:
        dependencies = dn.get('build-depends', [])

    log(dn, 'Installing dependencies\n', dependencies, verbose=True)
    shuffle(dependencies)
    for it in dependencies:
        dependency = app.defs.get(it)
        if os.path.exists(os.path.join(dn['sandbox'], 'baserock',
                                       dependency['name'] + '.meta')):
            # dependency has already been installed
            log(dn, 'Already did', dependency['name'], verbose=True)
            continue

        install_dependencies(dn, dependency.get('build-depends', []))
        if (it in dn['build-depends']) or \
            (dependency.get('build-mode', 'staging') ==
                dn.get('build-mode', 'staging')):
            compose(dependency)
            if dependency.get('contents'):
                install_dependencies(dn, dependency['contents'])
            sandbox.install(dn, dependency)
    if config.get('log-verbose'):
        sandbox.list_files(dn)


def build(dn):
    '''Create an artifact for a single component and add it to the cache'''

    if get_cache(dn):
        return

    with claim(dn):
        if dn.get('kind', 'chunk') == 'chunk':
            install_dependencies(dn)
        with timer(dn, 'build of %s' % dn['cache']):
            run_build(dn)

        with timer(dn, 'artifact creation'):

            if dn.get('kind', 'chunk') == 'system':
                install_split_artifacts(dn)

            write_metadata(dn)
            cache(dn)


def run_build(dn):
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
        dn['SOURCE_DATE_EPOCH'] = repos.source_date_epoch(dn['checkout'])

    get_build_commands(dn)
    env_vars = sandbox.env_vars_for_build(dn)

    log(dn, 'Logging build commands to %s' % dn['log'])
    for build_step in app.defs.defaults.build_steps:
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
def claim(dn):
    with open(lockfile(dn), 'a') as l:
        try:
            fcntl.flock(l, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as e:
            if e.errno in (errno.EACCES, errno.EAGAIN):
                # flock() will report EACCESS or EAGAIN when the lock fails.
                raise RetryException(dn)
            else:
                log(dn, 'ERROR: surprise exception in assembly', '')
                import traceback
                traceback.print_exc()
                log(dn, 'Sandbox debris at', dn['sandbox'], exit=True)
        try:
            yield
        finally:
            if os.path.isfile(lockfile(dn)):
                os.remove(lockfile(dn))


def get_build_commands(dn):
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
        dn['install-commands'] = gather_integration_commands(dn)
        return

    exit = True if config.get('check-definitions') == 'exit' else False
    if 'build-system' in dn:
        bs = dn['build-system']
        log(dn, 'Defined build system is', bs)
    else:
        files = os.listdir(dn['checkout'])
        bs = app.defs.defaults.detect_build_system(files)
        if bs == 'manual' and 'install-commands' not in dn:
            if dn.get('kind', 'chunk') == 'chunk':
                print(dn)
                log(dn, 'WARNING: No install-commands, manual build-system',
                    exit=exit)
        log(dn, 'WARNING: Assumed build system is', bs)

    for build_step in app.defs.defaults.build_steps:
        if dn.get(build_step, None) is None:
            commands = app.defs.defaults.build_systems[bs].get(build_step, [])
            dn[build_step] = commands


def gather_integration_commands(dn):
    # 1. iterate all subcomponents (recursively) looking for sys-int commands
    # 2. gather them all up
    # 3. asciibetically sort them
    # 4. concat the lists

    def _gather_recursively(component, commands):
        if 'system-integration' in component:
            for product, it in component['system-integration'].items():
                for name, cmdseq in it.items():
                    commands["%s-%s" % (name, product)] = cmdseq
        for subcomponent in component.get('contents', []):
            _gather_recursively(app.defs.get(subcomponent), commands)

    all_commands = {}
    _gather_recursively(dn, all_commands)
    result = []
    for key in sorted(list(all_commands.keys())):
        result.extend(all_commands[key])
    return result
