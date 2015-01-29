#!/usr/bin/env python3
#
# Copyright (C) 2012 - 2014  Codethink Limited
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

import app
import os
import stat
import shutil
import cache
from subprocess import check_output
from subprocess import call
import sandbox


class StagingArea(object):

    _base_path = ['/sbin', '/usr/sbin', '/bin', '/usr/bin']

    def __init__(self, this, build_env, use_chroot=True, extra_env={},
                 extra_path=[]):
        this['build'] = os.path.join(app.settings['assembly'], this['name']
                                     + '.build')
        this['install'] = os.path.join(app.settings['assembly'], this['name']
                                       + '.inst')
        os.makedirs(this['build'])
        os.makedirs(this['install'])
        self.build = this['build']
        self.install = this['install']

        self.dirname = this['name']
        self.builddirname = None
        self.destdirname = None
        self._bind_readonly_mount = None

        self.use_chroot = use_chroot
        self.env = build_env.env
        self.env.update(extra_env)

        if use_chroot:
            path = extra_path + build_env.extra_path + self._base_path
        else:
            rel_path = extra_path + build_env.extra_path
            full_path = [os.path.normpath(dirname + p) for p in rel_path]
            path = full_path + os.environ['PATH'].split(':')
        self.env['PATH'] = ':'.join(path)

    def install_artifact(self, component):
        app.log(component, 'Installing artifact')
        unpackdir = self._unpack_artifact(component)
        self._hardlink_all_files(unpackdir, app.settings['assembly'])

    def _unpack_artifact(self, component):
        cachefile = cache.get_cache(component)
        if cachefile:
            unpackdir = cachefile + '.unpacked'
            if not os.path.exists(unpackdir):
                os.makedirs(unpackdir)
                call(['tar', 'xf', cachefile, '--directory', unpackdir])
            return unpackdir

        return False

    def _hardlink_all_files(self, srcpath, destpath):
        '''Hardlink every file in the path to the staging-area

        If an exception is raised, the staging-area is indeterminate.

        '''

        file_stat = os.lstat(srcpath)
        mode = file_stat.st_mode

        if stat.S_ISDIR(mode):
            # Ensure directory exists in destination, then recurse.
            if not os.path.lexists(destpath):
                os.makedirs(destpath)
            dest_stat = os.stat(os.path.realpath(destpath))
            if not stat.S_ISDIR(dest_stat.st_mode):
                raise IOError('Destination not a directory. source has %s'
                              ' destination has %s' % (srcpath, destpath))

            for entry in os.listdir(srcpath):
                self._hardlink_all_files(os.path.join(srcpath, entry),
                                         os.path.join(destpath, entry))
        elif stat.S_ISLNK(mode):
            # Copy the symlink.
            if os.path.lexists(destpath):
                os.remove(destpath)
            os.symlink(os.readlink(srcpath), destpath)

        elif stat.S_ISREG(mode):
            # Hardlink the file.
            if os.path.lexists(destpath):
                os.remove(destpath)
            os.link(srcpath, destpath)

        elif stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
            # Block or character device. Put contents of st_dev in a mknod.
            if os.path.lexists(destpath):
                os.remove(destpath)
            os.mknod(destpath, file_stat.st_mode, file_stat.st_rdev)
            os.chmod(destpath, file_stat.st_mode)

        else:
            # Unsupported type.
            raise IOError('Cannot extract %s into staging-area. Unsupported'
                          ' type.' % srcpath)
