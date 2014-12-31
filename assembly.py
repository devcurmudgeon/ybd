#!/usr/bin/env python3
#
# Copyright (C) 2014  Codethink Limited
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

def extra_env(this):
    env = {}
    env['DESTDIR'] = this.get('install')
    env['PREFIX'] = this.get('prefix') or '/usr'
    env['MAKEFLAGS'] = '-j%s' % (this.get('max_jobs') or
                                 app.settings['max_jobs'])
    if this.get('build-mode') == 'bootstrap':
        tools_path = os.path.join(app.settings['assembly'], 'tools/bin')
        print(tools_path)
        if os.path.exists(tools_path):
            env['PATH'] = '%s:%s' % ( tools_path, os.environ['PATH'] )
            app.log(this, 'path is', env['PATH'])
    return env

def build(this):
    ''' Do the actual creation of an artifact.

    By the time we get here, all dependencies for 'this' have been assembled.

    '''

    app.log(this, 'Start build')

    defs = Definitions()

    build_env = BuildEnvironment(app.settings, extra_env(this))
    with sandbox.setup(this['build'], build_env.env):
        call(['env'])
        if defs.lookup(this, 'repo') != []:
            repos.checkout(this)
            get_upstream_version(defs, this)
            get_build_system_commands(defs, this)

            for command in defs.lookup(this, 'configure-commands'):
                sandbox.run_cmd(this, command)

            for command in defs.lookup(this, 'build-commands'):
                sandbox.run_cmd(this, command)

            for command in defs.lookup(this, 'install-commands'):
                sandbox.run_cmd(this, command)

        cache.cache(this)


def get_upstream_version(defs, this):
    last_tag = 'No tag found'
    try:
        with open(os.devnull, "w") as fnull:
            last_tag = check_output(['git', 'describe', '--abbrev=0',
                                     '--tags', this['ref']],
                                    stderr=fnull)[0:-1]
    except:
        pass

    if defs.lookup(this, 'ref') or last_tag:
        app.log(this, 'Upstream version: %s (%s)' % (this['ref'][:8],
                                                     last_tag))


def get_build_system_commands(defs, this):
    file_list = check_output(['ls']).decode("utf-8").splitlines()
    build_system = buildsystem.detect_build_system(file_list)
    for commands in ['configure-commands', 'build-commands',
                     'install-commands']:
        if defs.lookup(this, commands) == []:
            this[commands] = build_system.commands[commands]
