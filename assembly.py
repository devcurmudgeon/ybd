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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# =*= License: GPL-2 =*=

import os
from definitions import Definitions
import cache
from staging import StagingArea
import repos
import app
import buildsystem
from buildenvironment import BuildEnvironment
import sandbox
from subprocess import check_output
from subprocess import call


build_steps = ['pre-configure-commands',
               'configure-commands',
               'post-configure-commands',
               'pre-build-commands',
               'build-commands',
               'post-build-commands',
               'pre-test-commands',
               'test-commands',
               'post-test-commands',
               'pre-install-commands',
               'install-commands',
               'post-install-commands']


def assemble(target):
    '''Assemble dependencies and contents recursively until target exists.'''
    if cache.get_cache(target):
        app.log(target, 'Cache found', cache.get_cache(target))
        return

    defs = Definitions()
    this = defs.get(target)
    if defs.lookup(this, 'repo') != [] and defs.lookup(this, 'tree') == []:
        this['tree'] = repos.get_tree(this)

    with app.timer(this, 'Starting assembly'):
        build_env = BuildEnvironment(app.settings)
        stage = StagingArea(this, build_env)
        for dependency in defs.lookup(this, 'build-depends'):
            assemble(defs.get(dependency))
            stage.install_artifact(dependency, app.settings['assembly'])

        # if we're distbuilding, wait here for all dependencies to complete
        # how do we know when that happens?

        for component in defs.lookup(this, 'contents'):
            assemble(defs.get(component))
            stage.install_artifact(component, this['install'])

        build_env = clean_env(this)
        with sandbox.setup(this, build_env):
            build(this)


def build(this):
    ''' Do the actual creation of an artifact.

    By the time we get here, all dependencies for 'this' have been assembled.

    '''

    app.log(this, 'Start build')

    defs = Definitions()
    if defs.lookup(this, 'repo') != []:
        repos.checkout(this)

    get_build_system_commands(defs, this)
    for build_step in build_steps:
        if defs.lookup(this, build_step):
            app.log(this, 'Running', build_step)
        for command in defs.lookup(this, build_step):
            sandbox.run_cmd(this, command)

    cache.cache(this)
    sandbox.cleanup(this)


def get_build_system_commands(defs, this):
    build_system = None
    has_commands = False

    # if bs is unspecified and all steps are empty, detect bs & use its commands
    # if bs is specified, use its commands for empty steps

    # this logic is rather convoluted, because there are examples of morph files
    # where build-system is unspecified. it boils down to:
    #     if bs is specified, or all steps are empty, fill any empty steps

    for bs in buildsystem.build_systems:
        if this.get('build-system') == bs.name:
            build_system = bs

    if not build_system:
        for build_step in build_steps:
            if defs.lookup(this, build_step) != []:
                return

        files = check_output(['ls', this['build']]).decode("utf-8").splitlines()
        build_system = buildsystem.detect_build_system(files)

    for build_step in build_steps:
        if defs.lookup(this, build_step) == []:
            if build_system.commands.get(build_step):
                this[build_step] = build_system.commands.get(build_step)


def clean_env(this):
    env = {}
    extra_path = []
    _base_path = ['/sbin', '/usr/sbin', '/bin', '/usr/bin']
    defs = Definitions()

    if app.settings['no-ccache']:
        ccache_path = []
    else:
        ccache_path = ['/usr/lib/ccache']
        env['CCACHE_DIR'] = '/tmp/ccache'
        env['CCACHE_EXTRAFILES'] = ':'.join(
            f for f in ('/baserock/binutils.meta',
                        '/baserock/eglibc.meta',
                        '/baserock/gcc.meta') if os.path.exists(f))
        if not app.settings.get('no-distcc'):
            env['CCACHE_PREFIX'] = 'distcc'

    prefixes = [this.get('prefix', '/usr')]

    for name in defs.lookup(this, 'build-depends'):
        dependency = defs.get(name)
        prefixes.append(defs.lookup(dependency, 'prefix'))
    prefixes = set(prefixes)
    for prefix in prefixes:
        if prefix:
            bin_path = os.path.join(prefix, 'bin')
            extra_path += [bin_path]

    if this.get('build-mode', 'staging') == 'staging':
        path = extra_path + ccache_path + _base_path
    else:
        rel_path = extra_path + ccache_path
        full_path = [os.path.normpath(app.settings['assembly'] + p)
                     for p in rel_path]
        path = full_path + os.environ['PATH'].split(':')
    env['PATH'] = ':'.join(path)

    if this.get('build-mode') == 'bootstrap':
        env['DESTDIR'] = this.get('install')
    else:
        env['DESTDIR'] = os.path.join('/',
                                      os.path.basename(this.get('install')))

    env['PREFIX'] = this.get('prefix') or '/usr'

    env['MAKEFLAGS'] = '-j%s' % (this.get('max_jobs') or
                                 app.settings['max_jobs'])
#    env['MAKEFLAGS'] = '-j1'

    env['TERM'] = 'dumb'
    env['SHELL'] = '/bin/sh'
    env['USER'] = env['USERNAME'] = env['LOGNAME'] = 'tomjon'
    env['LC_ALL'] = 'C'
    env['HOME'] = '/tmp/'

    arch = app.settings['arch']
    cpu = 'i686' if arch == 'x86_32' else arch
    abi = 'eabi' if arch.startswith('arm') else ''
    env['TARGET'] = cpu + '-baserock-linux-gnu' + abi
    env['TARGET_STAGE1'] = cpu + '-bootstrap-linux-gnu' + abi
    env['MORPH_ARCH'] = arch

    return env
