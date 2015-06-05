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
from definitions import Definitions
import cache
import app
from assembly import assemble, deploy
import sandbox
import platform


print('')
if len(sys.argv) not in [2,3]:
    sys.stderr.write("Usage: %s DEFINITION_FILE [ARCH]\n\n" % sys.argv[0])
    sys.exit(1)

target = sys.argv[1]
if len(sys.argv) == 3:
    arch = sys.argv[2]
else:
    arch = platform.machine()

with app.setup(target, arch):
    with app.timer('TOTAL', 'YBD starts, version %s' %
                   app.settings['ybd-version']):
        app.log('TARGET', 'Target is %s' % os.path.join(app.settings['defdir'],
                                                      target), arch)
        with app.timer('DEFINITIONS', 'Parsing %s' % app.settings['def-ver']):
            defs = Definitions()
        with app.timer('CACHE-KEYS', 'Calculating'):
            cache.get_cache(app.settings['target'])
        defs.save_trees()
        assemble(app.settings['target'])
        deploy(app.settings['target'])
