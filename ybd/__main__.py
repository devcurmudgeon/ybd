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
from ybd import app, cache, sandbox
from ybd.app import cleanup, RetryException, setup, spawn
from ybd.assembly import compose
from ybd import config
from ybd.deployment import deploy
from ybd.pots import Pots
from ybd.concourse import Pipeline
from ybd.release_note import do_release_note
from ybd.utils import log, timer
import sandboxlib
import yaml


def write_cache_key():
    with open(config.config['result-file'], 'w') as f:
        f.write(target['cache'] + '\n')
    for kind in ['systems', 'strata', 'chunks']:
        log('COUNT', '%s has %s %s' % (config.config['target'],
                                       config.config[kind], kind))
    log('RESULT', 'Cache-key for target is at', config.config['result-file'])


print('')
original_cwd = os.getcwd()
if not os.path.exists('./VERSION'):
    if os.path.basename(os.getcwd()) != 'definitions':
        if os.path.isdir(os.path.join(os.getcwd(), 'definitions')):
            os.chdir(os.path.join(os.getcwd(), 'definitions'))
        else:
            if os.path.isdir(os.path.join(os.getcwd(), '..', 'definitions')):
                os.chdir(os.path.join(os.getcwd(), '..', 'definitions'))

setup(sys.argv, original_cwd)
cleanup(config.config['tmp'])

with timer('TOTAL'):
    tmp_lock = open(os.path.join(config.config['tmp'], 'lock'), 'r')
    fcntl.flock(tmp_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)

    target = os.path.join(config.config['defdir'], config.config['target'])
    log('TARGET', 'Target is %s' % target, config.config['arch'])
    with timer('DEFINITIONS', 'parsing %s' % config.config['def-version']):
        config.defs = Pots()

    target = config.defs.get(config.config['target'])
    if config.config.get('mode', 'normal') == 'parse-only':
        Pipeline(target)
        os._exit(0)

    with timer('CACHE-KEYS', 'cache-key calculations'):
        cache.cache_key(target)

    if 'release-note' in config.config:
        do_release_note(config.config['release-note'])

    if config.config['total'] == 0 or (config.config['total'] == 1 and
                                       target.get('kind') == 'cluster'):
        log('ARCH', 'No definitions for', config.config['arch'], exit=True)

    config.defs.save_trees()
    if config.config.get('mode', 'normal') == 'keys-only':
        write_cache_key()
        os._exit(0)

    cache.cull(config.config['artifacts'])

    sandbox.executor = sandboxlib.executor_for_platform()
    log(config.config['target'], 'Sandbox using %s' % sandbox.executor)
    if sandboxlib.chroot == sandbox.executor:
        log(config.config['target'], 'WARNING: using chroot is less safe ' +
            'than using linux-user-chroot')

    if 'instances' in config.config:
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

    if config.config.get('reproduce'):
        log('REPRODUCED', 'Matched %s of' %
            len(config.config['reproduced']), config.config['tasks'])
        for match in config.config['reproduced']:
            print(match[0], match[1])

    if target.get('kind') == 'cluster' and config.config.get('fork') is None:
        with timer(target, 'cluster deployment'):
            deploy(target)
