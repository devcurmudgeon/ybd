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
import repos
import app
import buildsystem
import sandbox
from subprocess import check_output
from subprocess import call


def assemble(target):
    '''Assemble dependencies and contents recursively until target exists.'''
    if cache.get_cache(target):
        return

    defs = Definitions()
    this = defs.get(target)

    with app.timer(this, 'Starting assembly'):
        with sandbox.setup(this):
            for it in this.get('build-depends', []):
                dependency = defs.get(it)
                assemble(dependency)
                sandbox.install(this, dependency)

            for it in this.get('contents', []):
                component = defs.get(it)
                if component.get('build-mode') == 'bootstrap':
                    continue
                assemble(component)
                sandbox.install(this, component)

            if this.get('build-mode') != 'bootstrap':
                sandbox.ldconfig(this)
            else:
                app.log(this, "No ldconfig because bootstrap mode is engaged")

            build(this)
            if this.get('devices'):
                sandbox.create_devices(this)
            do_manifest(this)

            cache.cache(this)
            sandbox.remove(this)


def build(this):
    '''Actually create an artifact and add it to the cache

    This is what actually runs ./configure, make, make install (for example)
    By the time we get here, all dependencies for 'this' have been assembled.
    '''

    app.log(this, 'Start build')
    defs = Definitions()
    if this.get('repo'):
        repos.checkout(this['name'], this['repo'], this['ref'], this['build'])

    get_build_commands(this)
    for build_step in buildsystem.build_steps:
        if this.get(build_step):
            app.log(this, 'Running', build_step)
        for command in this.get(build_step, []):
            sandbox.run_sandboxed(this, command)


def get_build_commands(this):
    '''Get commands specified in this, plus commmands implied by build_system

    If bs is unspecified and all steps are empty, detect bs & use its commands
    If bs is specified, use its commands for empty steps

    This logic is rather convoluted, because there are examples of morph files
    where build-system is unspecified. It boils down to:
        if bs is specified, or all steps are empty, fill any empty steps
    '''

    build_system = None
    for bs in buildsystem.build_systems:
        if this.get('build-system') == bs.name:
            build_system = bs

    if not build_system:
        for build_step in buildsystem.build_steps:
            if this.get(build_step):
                return

        files = check_output(['ls', this['build']]).decode("utf-8").splitlines()
        build_system = buildsystem.detect_build_system(files)

    for build_step in buildsystem.build_steps:
        if this.get(build_step, None) is None:
            if build_system.commands.get(build_step):
                this[build_step] = build_system.commands.get(build_step)


def do_manifest(this):
    metafile = os.path.join(this['baserockdir'], this['name'] + '.meta')
    with app.chdir(this['install']), open(metafile, "w") as f:
        call(['find'], stdout=f, stderr=f)
