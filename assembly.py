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
    defs = Definitions()
    this = defs.get(target)
    if defs.lookup(this, 'repo') != [] and defs.lookup(this, 'tree') == []:
        this['tree'] = repos.get_tree(this)

    if cache.get_cache(this):
        app.log(this, 'Cache found', cache.get_cache(this))
        return

    with app.timer(this, 'Starting assembly'):
        build_env = BuildEnvironment(app.settings)
        stage = StagingArea(this, build_env)
        for dependency in defs.lookup(this, 'build-depends'):
            assemble(defs.get(dependency))
            stage.install_artifact(dependency)

        # if we're distbuilding, wait here for all dependencies to complete
        # how do we know when that happens?

        for component in defs.lookup(this, 'contents'):
            assemble(defs.get(component))

        build(this)


def build(this):
    ''' Do the actual creation of an artifact.

    By the time we get here, all dependencies for 'this' have been assembled.

    '''

    app.log(this, 'Start build')

    defs = Definitions()

    build_env = BuildEnvironment(app.settings, extra_env(this))
    with sandbox.setup(this, build_env):
        if defs.lookup(this, 'repo') != []:
            repos.checkout(this)
            get_build_system_commands(defs, this)
            for build_step in build_steps:
                if defs.lookup(this, build_step):
                    app.log(this, 'Running', build_step)
                for command in defs.lookup(this, build_step):
                    sandbox.run_cmd(this, command)

        cache.cache(this)


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


def extra_env(this):
    env = {}
    extra_path = []
    _base_path = ['/sbin', '/usr/sbin', '/bin', '/usr/bin']
    defs = Definitions()

    prefixes = set(defs.get(a).get('prefix') for a in
                   defs.lookup(this, 'build-depends'))
    for d in prefixes:
        if d:
            bin_path = os.path.join(d, 'bin')
            extra_path += [bin_path]

    ccache_path = ['/usr/lib/ccache'] if not app.settings['no-ccache'] else []

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
    env['MAKEFLAGS'] = '-j1'
    return env
