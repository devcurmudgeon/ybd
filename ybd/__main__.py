#!/usr/bin/env python
# Copyright (C) 2014-2016  Codethink Limited
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
from assembly import compose
from deployment import deploy
from definitions import Definitions
import cache
import sandbox
import sandboxlib
import yaml


# copied from http://stackoverflow.com/questions/21016220
class ExplicitDumper(yaml.SafeDumper):
    """
    A dumper that will never emit aliases.
    """

    def ignore_aliases(self, data):
        return True


def write_yaml():
    with open(app.config['result-file'], 'w') as f:
        f.write(yaml.dump(app.defs._data, default_flow_style=False,
                          Dumper=ExplicitDumper))
    app.log('RESULT', 'Parsed definitions data in yaml format is at',
            app.config['result-file'])


def write_cache_key():
    with open(app.config['result-file'], 'w') as f:
        f.write(target['cache'] + '\n')
    app.log('RESULT', 'Cache-key for target is at',
            app.config['result-file'])


print('')
if not os.path.exists('./VERSION'):
    if os.path.basename(os.getcwd()) != 'definitions':
        if os.path.isdir(os.path.join(os.getcwd(), 'definitions')):
            os.chdir(os.path.join(os.getcwd(), 'definitions'))
        else:
            if os.path.isdir(os.path.join(os.getcwd(), '..', 'definitions')):
                os.chdir(os.path.join(os.getcwd(), '..', 'definitions'))

app.setup(sys.argv)
app.cleanup(app.config['tmp'])

with app.timer('TOTAL'):
    tmp_lock = open(os.path.join(app.config['tmp'], 'lock'), 'r')
    fcntl.flock(tmp_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)

    target = os.path.join(app.config['defdir'], app.config['target'])
    app.log('TARGET', 'Target is %s' % target, app.config['arch'])
    with app.timer('DEFINITIONS', 'parsing %s' % app.config['def-version']):
        app.defs = Definitions()
    target = app.defs.get(app.config['target'])

    if app.config.get('mode', 'normal') == 'parse-only':
        write_yaml()
        os._exit(0)

    with app.timer('CACHE-KEYS', 'cache-key calculations'):
        cache.cache_key(target)

    if app.config['total'] == 0 or (app.config['total'] == 1 and
                                    target.get('kind') == 'cluster'):
        app.exit('ARCH', 'ERROR: no definitions found for', app.config['arch'])

    app.defs.save_trees()
    if app.config.get('mode', 'normal') == 'keys-only':
        write_cache_key()
        os._exit(0)

    cache.cull(app.config['artifacts'])

    sandbox.executor = sandboxlib.executor_for_platform()
    app.log(app.config['target'], 'Sandbox using %s' % sandbox.executor)
    if sandboxlib.chroot == sandbox.executor:
        app.log(app.config['target'], 'WARNING: using chroot is less safe ' +
                'than using linux-user-chroot')

    if 'instances' in app.config:
        app.spawn()

    while True:
        try:
            compose(target)
            break
        except KeyboardInterrupt:
            app.log(target, 'Interrupted by user')
            os._exit(1)
        except app.RetryException:
            pass
        except:
            import traceback
            traceback.print_exc()
            app.log(target, 'Exiting: uncaught exception')
            os._exit(1)

    if app.config.get('reproduce'):
        app.log('REPRODUCED',
                'Matched %s of' % len(app.config['reproduced']),
                app.config['tasks'])
        for match in app.config['reproduced']:
            print match[0], match[1]

    if target.get('kind') == 'cluster' and app.config.get('fork') is None:
        with app.timer(target, 'cluster deployment'):
            deploy(target)
