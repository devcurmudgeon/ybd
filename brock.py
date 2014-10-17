#!/usr/bin/python
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

import yaml
import os
import sys
import hashlib
import datetime
import tempfile
from subprocess import call
import defs
import cache
import app


definitions = []


def teardown():
    #  assuming success, we can remove the 'assembly' directory
    pass


def assemble(definitions, this):
    ''' Do the actual creation of an artifact.

    By the time we get here, all dependencies for 'this' have been assembled.

    '''
    app.log('assemble', this)
    cache.checkout(this)

    os.chdir(app.config['assembly'])
    # run the configure-commands
    app.log('configure-commands', this)
    # print get(this,'configure-commands')

    # run the build-commands
    app.log('build-commands', this)
    # print get(this,'build-commands')

    # run the install-commands
    app.log('install-commands', this)
    # print get(this,'install-commands')

    # cache the result
    app.log('cache', this)
    cache.cache(definitions, this)


def build(definitions, target):
    ''' Build dependencies and content recursively until target is cached. '''
#    app.log('starting build', target)
    if cache.is_cached(definitions, target):
        app.log('is already cached as', target,
                cache.is_cached(definitions, target))
        return

    this = defs.get_def(definitions, target)

    for dependency in defs.get(this, 'build-depends'):
        build(definitions, dependency)

    # wait here for all the dependencies to complete
    # how do we know when that happens?

    for content in defs.get(this, 'contents'):
        build(definitions, content)

    assemble(definitions, this)


path, target = os.path.split(sys.argv[1])
target = target.replace('.def', '')
target = target.replace('.morph', '')
app.setup(target)
defs.load_defs(path, definitions)
build(definitions, target)
teardown()
