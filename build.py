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
import app
import buildsystem
from subprocess import check_output
from subprocess import call


def assemble(target):
    '''Assemble dependencies and contents recursively until target exists.'''
    defs = Definitions()
    this = defs.get(target)
    if defs.lookup(this, 'repo') != []:
        this['tree'] = cache.get_tree(this)

    if cache.is_cached(this):
        app.log(this, 'Cache found', cache.is_cached(this))
        return

    with app.timer(this, 'Starting assembly'):
        for dependency in defs.lookup(this, 'build-depends'):
            assemble(defs.get(dependency))

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
    this['build'] = os.path.join(app.config['assembly'], this['name']
                                 + '.build')
    try:
        os.makedirs(this['build'])
    except:
        app.log(this, 'Re-using existing build dir', this['build'])

    defs = Definitions()
    with app.chdir(this['build']):
        if defs.lookup(this, 'repo') != []:
            cache.checkout(this)
            try:
                file_list = check_output(['ls'])
                build_system = buildsystem.detect_build_system(file_list)
                for commands in ['configure-commands',
                                 'build-commands',
                                 'install-commands']:
                    if defs.lookup(this, commands) == []:
                        this[commands] = build_system.commands[commands]
            except:
                app.log(this, 'Build system is not recognised')

            try:
                with open(os.devnull, "w") as fnull:
                    last_tag = check_output(['git', 'describe', '--abbrev=0',
                                             '--tags', this['ref']],
                                            stderr=fnull)[0:-1]
                app.log(this, 'Upstream version', last_tag.decode("utf-8"))
            except:
                if defs.lookup(this, 'ref'):
                    app.log(this, 'Upstream version', this['ref'][:8])

            for command in defs.lookup(this, 'configure-commands'):
                call(['sh', '-c', command])

            for command in defs.lookup(this, 'build-commands'):
                call(['sh', '-c', command])

            for command in defs.lookup(this, 'install-commands'):
                app.log(this, 'install commands', command)

        cache.cache(this)
