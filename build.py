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


def build(target):
    ''' Build dependencies and component recursively until this is cached. '''
    defs = Definitions()
    this = defs.get(target)
    if defs.lookup(this, 'repo') != []:
        this['tree'] = cache.get_tree(this)

    if cache.is_cached(this):
        app.log(this, 'Cache found', cache.is_cached(this))
        return

    with app.timer(this, 'Starting build'):
        for dependency in defs.lookup(this, 'build-depends'):
            build(defs.get(dependency))

        # if we're distbuilding, wait here for all dependencies to complete
        # how do we know when that happens?

        for component in defs.lookup(this, 'contents'):
            build(defs.get(component))

        assemble(this)


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
#                app.log(this, 'Build system', build_system)

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

            # run the configure-commands
            # run the build-commands
            # run the install-commands

        # cache the result
        cache.cache(this)
