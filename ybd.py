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

'''A module to build a definition.'''

import os
import sys
import defs
import cache
import app
import buildsystem
from subprocess import check_output


def assemble(definitions, this):
    ''' Do the actual creation of an artifact.

    By the time we get here, all dependencies for 'this' have been assembled.

    '''

    with app.chdir(app.config['assembly']):

        app.log(this, 'assemble', app.config['assembly'])
        cache.checkout(this)
        with app.chdir(this['build']):
            try:
                file_list = check_output(['git', 'ls-tree', '--name-only',
                                          this['ref']],
                                         universal_newlines=True)
                build_system = buildsystem.detect_build_system(file_list)
                app.log(this, 'build system', build_system)

            except:
                app.log(this, 'build system is not recognised')

        # run the configure-commands
#        app.log(this, 'configure-commands',
#                defs.lookup(this, 'configure-commands'))

        # run the build-commands
#        app.log(this, 'build-commands', defs.lookup(this, 'build-commands'))

        # run the install-commands
#        app.log(this, 'install-commands', defs.lookup(this,
#                                                      'install-commands'))

        # cache the result
#        app.log(this, 'cache')
        cache.cache(definitions, this)


def build(definitions, target):
    ''' Build dependencies and content recursively until target is cached. '''
    with app.timer(target):
        app.log(target, 'starting build')
        if cache.is_cached(definitions, target):
            app.log(target, 'is already cached as',
                    cache.is_cached(definitions, target))
            return

        this = defs.get_def(definitions, target)

        for dependency in defs.lookup(this, 'build-depends'):
            build(definitions, dependency)

        # wait here for all the dependencies to complete
        # how do we know when that happens?

        for content in defs.lookup(this, 'contents'):
            build(definitions, content)

        assemble(definitions, this)


path, target = os.path.split(sys.argv[1])
target = target.replace('.def', '')
with app.timer('TOTAL'):
    with app.setup(target):
        definitions = []
        defs.load_defs(definitions)
#        for definition in definitions:
#            app.log(definition['name'], 'hash', definition['hash'])
        build(definitions, target)
