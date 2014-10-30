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

import contextlib
import os
import datetime
import defs
import shutil
from subprocess import check_output

config = {}

def log(component, message, data=''):
    ''' Print a timestamped log. '''
    name = defs.get(component, 'name')
    if name == []:
        name = component

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print('%s [%s] %s %s' % (timestamp, name, message, data))


@contextlib.contextmanager
def setup(target):
    try:
        config['DTR'] = check_output(['git', 'rev-parse', 'HEAD^{tree}'],
                                    universal_newlines=True)[0:-1]
        config['base'] = os.path.expanduser('~/.ybd/')
        config['caches'] = os.path.join(config['base'], 'caches')
        config['gits'] = os.path.join(config['base'], 'gits')
        config['staging'] = os.path.join(config['base'], 'staging')
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        config['assembly'] = os.path.join(config['staging'],
                                          target + '-' + timestamp)

        for directory in ['base', 'caches', 'gits', 'staging', 'assembly']:
            if not os.path.exists(config[directory]):
                os.mkdir(config[directory])

        # git replace means we can't trust that just the sha1 of a branch
        # is enough to say what it contains, so we turn it off by setting
        # the right flag in an environment variable.
        os.environ['GIT_NO_REPLACE_OBJECTS'] = '1'

        log(target, 'Config', config)

        yield

    finally:
        # assuming success, we can remove the 'assembly' directory
        # shutil.rmtree(config['assembly'])
        log(target, 'assembly directory is still at', config['assembly'])
        pass


@contextlib.contextmanager
def chdir(dirname=None):
    currentdir = os.getcwd()
    try:
        if dirname is not None:
            os.chdir(dirname)
        yield
    finally:
        os.chdir(currentdir)


@contextlib.contextmanager
def timer(this):
    starttime = datetime.datetime.now()
    try:
        yield
    finally:
        td = datetime.datetime.now() - starttime
        hours, remainder = divmod(int(td.total_seconds()), 60*60)
        minutes, seconds = divmod(remainder, 60)
        td_string = "%02d:%02d:%02d" % (hours, minutes, seconds)
        if td_string != "00:00:00":
            log(this, 'Elapsed time', td_string)
