#!/usr/bin/env python
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
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# =*= License: GPL-2 =*=

'''A module to build a definition.'''

import os
import sys
import fcntl
import app
from assembly import assemble
from deployment import deploy
from definitions import Definitions
import cache
import sandbox
import sandboxlib


print('')
with app.timer('TOTAL'):
    app.setup(sys.argv)

    app.cleanup(app.config['tmp'])

    lockfile = open(os.path.join(app.config['base'], 'lock'), 'r')
    fcntl.flock(lockfile, fcntl.LOCK_SH | fcntl.LOCK_NB)

    target = os.path.join(app.config['defdir'], app.config['target'])
    app.log('TARGET', 'Target is %s' % target, app.config['arch'])
    with app.timer('DEFINITIONS', 'parsing %s' % app.config['def-version']):
        defs = Definitions()
    with app.timer('CACHE-KEYS', 'cache-key calculations'):
        cache.cache_key(defs, app.config['target'])
    defs.save_trees()

    sandbox.executor = sandboxlib.executor_for_platform()
    app.log(app.config['target'], 'Sandbox using %s' % sandbox.executor)
    if sandboxlib.chroot == sandbox.executor:
        app.log(app.config['target'], 'WARNING: rogue builds in a chroot ' +
                'sandbox may overwrite your system')

    if app.config.get('instances'):
        app.spawn()

    assemble(defs, app.config['target'])
    deploy(defs, app.config['target'])
