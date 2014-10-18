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

import os
import datetime
import defs

config = {}


def setup(target):
    config['base'] = os.path.expanduser('~/.brock/')
    config['caches'] = os.path.join(config['base'], 'caches')
    config['gits'] = os.path.join(config['base'], 'gits')
    config['staging'] = os.path.join(config['base'], 'staging')
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    config['assembly'] = os.path.join(config['staging'],
                                      target + '-' + timestamp)

    for directory in ['base', 'caches', 'gits', 'staging', 'assembly']:
        if not os.path.exists(config[directory]):
            os.mkdir(config[directory])


def log(component, message, data=''):
    ''' Print a timestamped log. '''
    name = defs.get(component, 'name')
    if name == []:
        name = component

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print '%s [%s] %s %s' % (timestamp, name, message, data)