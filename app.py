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
import shutil
from subprocess import check_output
from subprocess import call
settings = {}


def log(component, message='', data=''):
    ''' Print a timestamped log. '''
    name = component
    try:
        name = component['name']
    except:
        pass

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print('%s [%s] %s %s' % (timestamp, name, message, data))


def run_cmd(this, command):
    log(this, 'Running command\n\n', command)
    with open(os.devnull, "w") as fnull:
        if call(['sh', '-c', command], stdout=fnull, stderr=fnull):
            log(this, 'ERROR: in directory %s command failed:' % os.getcwd(),
                command)
            raise SystemExit


@contextlib.contextmanager
def setup(target, arch):
    try:
        settings['arch'] = arch
        settings['no-ccache'] = True
        settings['cache-server-url'] = \
            'http://git.baserock.org:8080/1.0/sha1s?'
        settings['base'] = os.path.expanduser('~/.ybd/')
        if os.path.exists('/src'):
            settings['base'] = '/src'
        settings['caches'] = os.path.join(settings['base'], 'cache')
        settings['artifacts'] = os.path.join(settings['caches'],
                                             'ybd-artifacts')
        settings['gits'] = os.path.join(settings['caches'], 'gits')
        settings['staging'] = os.path.join(settings['base'], 'staging')
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        settings['assembly'] = os.path.join(settings['staging'],
                                            target + '-' + timestamp)

        for directory in ['base', 'caches', 'artifacts', 'gits',
                          'staging', 'assembly']:
            if not os.path.exists(settings[directory]):
                os.mkdir(settings[directory])

        # git replace means we can't trust that just the sha1 of a branch
        # is enough to say what it contains, so we turn it off by setting
        # the right flag in an environment variable.
        os.environ['GIT_NO_REPLACE_OBJECTS'] = '1'

        yield

    finally:
        # assuming success, we can remove the 'assembly' directory
        # shutil.rmtree(settings['assembly'])
        log(target, 'Assembly directory is still at', settings['assembly'])


@contextlib.contextmanager
def chdir(dirname=None, env={}):
    currentdir = os.getcwd()
    currentenv = {}
    try:
        if dirname is not None:
            os.chdir(dirname)
        for key, value in env.items():
            currentenv[key] = os.environ.get(key)
            os.environ[key] = value
        yield
    finally:
        for key, value in currentenv.items():
            if value:
                os.environ[key] = value
            else:
                del os.environ[key]
        os.chdir(currentdir)


@contextlib.contextmanager
def timer(this, start_message=''):
    starttime = datetime.datetime.now()
    log(this, start_message)
    try:
        yield
    finally:
        td = datetime.datetime.now() - starttime
        hours, remainder = divmod(int(td.total_seconds()), 60*60)
        minutes, seconds = divmod(remainder, 60)
        td_string = "%02d:%02d:%02d" % (hours, minutes, seconds)
        log(this, 'Elapsed time', td_string)
