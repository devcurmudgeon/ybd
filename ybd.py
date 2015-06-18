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
import platform
import sandbox


print('')
if len(sys.argv) not in [2, 3]:
    sys.stderr.write("Usage: %s DEFINITION_FILE [ARCH]\n\n" % sys.argv[0])
    sys.exit(1)

target = sys.argv[1]
if len(sys.argv) == 3:
    arch = sys.argv[2]
else:
    arch = platform.machine()
    if arch in ('mips', 'mips64'):
        if arch == 'mips':
            arch = 'mips32'
        if sys.byteorder == 'big':
            arch = arch + 'b'
        else:
            arch = arch + 'l'

with app.setup(target, arch):
    with app.timer('TOTAL', 'ybd starts, version %s' %
                   app.settings['ybd-version']):
        app.log('TARGET', 'Target is %s' % os.path.join(app.settings['defdir'],
                                                        target), arch)
        with app.timer('DEFINITIONS', 'Parsing %s' % app.settings['def-ver']):
            defs = Definitions()
        with app.timer('CACHE-KEYS', 'Calculating'):
            cache.get_cache(defs, app.settings['target'])
        defs.save_trees()

        sandbox.executor = sandboxlib.executor_for_platform()
        app.log(target, 'Using %s for sandboxing' % sandbox.executor)

        assemble(defs, app.settings['target'])
        deploy(defs, app.settings['target'])
