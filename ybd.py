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


import sandboxlib

import os
import sys

import app
from assembly import assemble, deploy
from definitions import Definitions
import cache
import sandbox


print('')

app.setup(sys.argv)
with app.timer('TOTAL', '%s starts, version %s' % (app.settings['program'],
               app.settings['program-version'])):
    app.log('TARGET', 'Target is %s' % os.path.join(app.settings['defdir'],
                                                    app.settings['target']),
                                                    app.settings['arch'])
    with app.timer('DEFINITIONS', 'Parsing %s' % app.settings['def-version']):
        defs = Definitions()
    with app.timer('CACHE-KEYS', 'Calculating'):
        cache.get_cache(defs, app.settings['target'])
    defs.save_trees()

    sandbox.executor = sandboxlib.executor_for_platform()
    app.log(app.settings['target'], 'Sandbox using %s' % sandbox.executor)

    assemble(defs, app.settings['target'])
    deploy(defs, app.settings['target'])
