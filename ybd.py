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
from definitions import Definitions
import cache
import app
import buildsystem
from subprocess import check_output
from subprocess import DEVNULL


def assemble(this):
    ''' Do the actual creation of an artifact.

    By the time we get here, all dependencies for 'this' have been assembled.

    '''

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
                file_list = check_output(['git', 'ls-tree', '--name-only',
                                          this['ref']],
                                         universal_newlines=True)
                build_system = buildsystem.detect_build_system(file_list)
                app.log(this, 'build system', build_system)

            except:
                app.log(this, 'build system is not recognised')

            try:
                last_tag = check_output(['git', 'describe', '--abbrev=0',
                                         '--tags', this['ref']],
                                        stdout=DEVNULL,
                                        stderr=DEVNULL)[0:-1]
                app.log(this, 'Upstream version', last_tag.decode("utf-8"))
            except:
                if defs.lookup(this, 'ref'):
                    app.log(this, 'Upstream version', this['ref'][:8])

            # run the configure-commands
            # run the build-commands
            # run the install-commands

        # cache the result
        cache.cache(this)


def build(this):
    ''' Build dependencies and component recursively until this is cached. '''
    defs = Definitions()
    definition = defs.get(this)
    if cache.is_cached(definition):
        app.log(this, 'cache found at', cache.is_cached(this))
        return

    with app.timer(this):
        app.log(this, 'starting build')
        for dependency in defs.lookup(definition, 'build-depends'):
            build(dependency)

        # wait here for all the dependencies to complete
        # how do we know when that happens?

        for component in defs.lookup(definition, 'components'):
            build(component)

        assemble(definition)


path, target = os.path.split(sys.argv[1])
target = target.replace('.def', '')
with app.timer('TOTAL'):
    with app.setup(target):
        defs = Definitions()
        definition = defs.get(target)
        build(definition)
