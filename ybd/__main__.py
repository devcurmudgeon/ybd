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
from app import cleanup, config, log, RetryException, setup, spawn, timer
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


def write_yaml(target):
    with open(config['result-file'], 'w') as f:
        f.write(yaml.dump(app.defs._data, default_flow_style=False,
                          Dumper=ExplicitDumper))
    log('RESULT', 'Dumped yaml definitions at', config['result-file'])
    if target:
        import concourse
        concourse.Pipeline(config['target'])


def write_cache_key():
    with open(config['result-file'], 'w') as f:
        f.write(target['cache'] + '\n')
    for kind in ['systems', 'strata', 'chunks']:
        log('COUNT', '%s has %s %s' % (config['target'], config[kind], kind))
    log('RESULT', 'Cache-key for target is at', config['result-file'])


print('')
if not os.path.exists('./VERSION'):
    if os.path.basename(os.getcwd()) != 'definitions':
        if os.path.isdir(os.path.join(os.getcwd(), 'definitions')):
            os.chdir(os.path.join(os.getcwd(), 'definitions'))
        else:
            if os.path.isdir(os.path.join(os.getcwd(), '..', 'definitions')):
                os.chdir(os.path.join(os.getcwd(), '..', 'definitions'))

setup(sys.argv)
cleanup(config['tmp'])

with timer('TOTAL'):
    tmp_lock = open(os.path.join(config['tmp'], 'lock'), 'r')
    fcntl.flock(tmp_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)

    target = os.path.join(config['defdir'], config['target'])
    log('TARGET', 'Target is %s' % target, config['arch'])
    with timer('DEFINITIONS', 'parsing %s' % config['def-version']):
        app.defs = Definitions()
    target = app.defs.get(config['target'])

    if config.get('mode', 'normal') == 'parse-only':
        write_yaml(target)
        os._exit(0)

    with timer('CACHE-KEYS', 'cache-key calculations'):
        cache.cache_key(target)

    if config['total'] == 0 or (config['total'] == 1 and
                                target.get('kind') == 'cluster'):
        exit('ARCH', 'ERROR: no definitions found for', config['arch'])

    app.defs.save_trees()
    write_cache_key()
    if config.get('mode', 'normal') == 'keys-only':
        os._exit(0)

    cache.cull(config['artifacts'])

    sandbox.executor = sandboxlib.executor_for_platform()
    log(config['target'], 'Sandbox using %s' % sandbox.executor)
    if sandboxlib.chroot == sandbox.executor:
        log(config['target'], 'WARNING: using chroot is less safe ' +
            'than using linux-user-chroot')

    if 'instances' in config:
        spawn()

    while True:
        try:
            compose(target)
            break
        except KeyboardInterrupt:
            log(target, 'Interrupted by user')
            os._exit(1)
        except RetryException:
            pass
        except:
            import traceback
            traceback.print_exc()
            log(target, 'Exiting: uncaught exception')
            os._exit(1)

    if config.get('reproduce'):
        log('REPRODUCED',
            'Matched %s of' % len(config['reproduced']), config['tasks'])
        for match in config['reproduced']:
            print match[0], match[1]

    if target.get('kind') == 'cluster' and config.get('fork') is None:
        with timer(target, 'cluster deployment'):
            deploy(target)
