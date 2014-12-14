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
                                       + '.install')
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

    # Wrapper to be overridden by unit tests.
    def _mkdir(self, dirname):
        os.makedirs(dirname)

    def _dir_for_source(self, source, suffix):
        dirname = os.path.join(self.dirname,
                               '%s.%s' % (str(source.name), suffix))
        self._mkdir(dirname)
        return dirname

    def builddir(self, source):
        '''Create a build directory for a given source project.

        Return path to directory.

        '''

        return self._dir_for_source(source, 'build')

    def destdir(self, source):
        '''Create an installation target directory for a given source project.

        This is meant to be used as $DESTDIR when installing chunks.
        Return path to directory.

        '''

        return self._dir_for_source(source, 'inst')

    def relative(self, filename):
        '''Return a filename relative to the staging area.'''

        if not self.use_chroot:
            return filename

        dirname = self.dirname
        if not dirname.endswith('/'):
            dirname += '/'

        assert filename.startswith(dirname)
        return filename[len(dirname) - 1:]  # include leading slash

    def run(self, args):
        # call(sandbox.containerised_cmdline(args))
        print(sandbox.containerised_cmdline(args))

    def install_artifact(self, component):
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

    def remove(self):
        '''Remove the entire staging area.

        Do not expect anything with the staging area to work after this
        method is called. Be careful about calling this method if
        the filesystem root directory was given as the dirname.

        '''

        shutil.rmtree(self.dirname)

    to_mount = (
        ('dev/shm', 'tmpfs', 'none'),
    )

    def ccache_dir(self, source):
        ccache_dir = self._app.settings['compiler-cache-dir']
        if not os.path.isdir(ccache_dir):
            os.makedirs(ccache_dir)
        # Get a path for the repo's ccache
        ccache_url = source.repo.url
        ccache_path = urlparse(ccache_url).path
        ccache_repobase = os.path.basename(ccache_path)
        if ':' in ccache_repobase:  # the basename is a repo-alias
            resolver = morphlib.repoaliasresolver.RepoAliasResolver(
                self._app.settings['repo-alias'])
            ccache_url = resolver.pull_url(ccache_repobase)
            ccache_path = urlparse(ccache_url).path
            ccache_repobase = os.path.basename(ccache_path)
        if ccache_repobase.endswith('.git'):
            ccache_repobase = ccache_repobase[:-len('.git')]

        ccache_repodir = os.path.join(ccache_dir, ccache_repobase)
        # Make sure that directory exists
        if not os.path.isdir(ccache_repodir):
            os.mkdir(ccache_repodir)
        # Get the destination path
        ccache_destdir = os.path.join(self.dirname, 'tmp', 'ccache')
        # Make sure that the destination exists. We'll create /tmp if necessary
        # to avoid breaking when faced with an empty staging area.
        if not os.path.isdir(ccache_destdir):
            os.makedirs(ccache_destdir)
        return ccache_repodir

    def chroot_open(self, source, setup_mounts):
        '''Setup staging area for use as a chroot.'''

        assert self.builddirname is None and self.destdirname is None

        builddir = self.builddir(source)
        destdir = self.destdir(source)
        self.builddirname = builddir
        self.destdirname = destdir

        return builddir, destdir

    def chroot_close(self):
        '''Undo changes by chroot_open.

        This should be called after the staging area is no longer needed.

        '''
        # No cleanup is currently required
        pass

    def runcmd(self, argv, **kwargs):  # pragma: no cover
        '''Run a command in a chroot in the staging area.'''
        assert 'env' not in kwargs
        kwargs['env'] = dict(self.env)
        if 'extra_env' in kwargs:
            kwargs['env'].update(kwargs['extra_env'])
            del kwargs['extra_env']

        ccache_dir = kwargs.pop('ccache_dir', None)

        chroot_dir = self.dirname if self.use_chroot else '/'
        temp_dir = kwargs["env"].get("TMPDIR", "/tmp")

        staging_dirs = [self.builddirname, self.destdirname]
        if self.use_chroot:
            staging_dirs += ["dev", "proc", temp_dir.lstrip('/')]
        do_not_mount_dirs = [os.path.join(self.dirname, d)
                             for d in staging_dirs]
        if not self.use_chroot:
            do_not_mount_dirs += [temp_dir]
        logging.debug("Not mounting dirs %r" % do_not_mount_dirs)

        mount_proc = self.use_chroot
        if ccache_dir and not self._app.settings['no-ccache']:
            ccache_target = os.path.join(
                self.dirname, kwargs['env']['CCACHE_DIR'].lstrip('/'))
            binds = ((ccache_dir, ccache_target),)
        else:
            binds = ()

        cmdline = morphlib.util.containerised_cmdline(
            argv, cwd=kwargs.pop('cwd', '/'),
            root=chroot_dir, mounts=self.to_mount,
            binds=binds, mount_proc=mount_proc,
            writable_paths=do_not_mount_dirs)
        try:
            if kwargs.get('logfile') is not None:
                logfile = kwargs.pop('logfile')
                teecmd = ['tee', '-a', logfile]
                return self._app.runcmd(cmdline, teecmd, **kwargs)
            else:
                return self._app.runcmd(cmdline, **kwargs)
        except cliapp.AppException as e:
            raise cliapp.AppException('In staging area %s: running '
                                      'command \'%s\' failed.' %
                                      (self.dirname, ' '.join(argv)))

    def abort(self):
        '''Handle what to do with a staging area in the case of failure.
           This may either remove it or save it for later inspection.
        '''
        # TODO: when we add the option to throw away failed builds,
        #       hook it up here

        dest_dir = os.path.join(self._app.settings['tempdir'],
                                'failed', os.path.basename(self.dirname))
        os.rename(self.dirname, dest_dir)
        self.dirname = dest_dir
