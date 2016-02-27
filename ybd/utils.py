# Copyright (C) 2011-2016  Codethink Limited
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

import gzip
import tarfile
import contextlib
import os
import shutil
import stat
from fs.osfs import OSFS
from fs.multifs import MultiFS
import calendar

import app

# The magic number for timestamps: 2011-11-11 11:11:11
default_magic_timestamp = calendar.timegm([2011, 11, 11, 11, 11, 11])


def set_mtime_recursively(root, set_time=default_magic_timestamp):
    '''Set the mtime for every file in a directory tree to the same.

    The aim is to make builds more predictable.

    '''

    for dirname, subdirs, basenames in os.walk(root.encode("utf-8"),
                                               topdown=False):
        for basename in basenames:
            pathname = os.path.join(dirname, basename)
            # we need the following check to ignore broken symlinks
            if os.path.exists(pathname):
                os.utime(pathname, (set_time, set_time))
        os.utime(dirname, (set_time, set_time))


def copy_all_files(srcpath, destpath):
    '''Copy every file in the source path to the destination.

    If an exception is raised, the staging-area is indeterminate.

    '''

    def _copyfun(inpath, outpath):
        with open(inpath, "r") as infh:
            with open(outpath, "w") as outfh:
                shutil.copyfileobj(infh, outfh, 1024*1024*4)
        shutil.copystat(inpath, outpath)

    _process_tree(srcpath, destpath, _copyfun)


def hardlink_all_files(srcpath, destpath):
    '''Hardlink every file in the path to the staging-area

    If an exception is raised, the staging-area is indeterminate.

    '''
    _process_tree(srcpath, destpath, os.link)


def _process_tree(srcpath, destpath, actionfunc):
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
            _process_tree(os.path.join(srcpath, entry),
                          os.path.join(destpath, entry),
                          actionfunc)
    elif stat.S_ISLNK(mode):
        # Copy the symlink.
        if os.path.lexists(destpath):
            import re
            path = re.search('/.*$', re.search('tmp[^/]+/.*$',
                             destpath).group(0)).group(0)
            app.config['new-overlaps'] += [path]
            os.remove(destpath)
        os.symlink(os.readlink(srcpath), destpath)

    elif stat.S_ISREG(mode):
        # Process the file.
        if os.path.lexists(destpath):
            os.remove(destpath)
        actionfunc(srcpath, destpath)

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


def copy_file_list(srcpath, destpath, filelist):
    '''Copy every file in the source path to the destination.

    If an exception is raised, the staging-area is indeterminate.

    '''

    def _copyfun(inpath, outpath):
        with open(inpath, "r") as infh:
            with open(outpath, "w") as outfh:
                shutil.copyfileobj(infh, outfh, 1024*1024*4)
        shutil.copystat(inpath, outpath)

    _process_list(srcpath, destpath, filelist, _copyfun)


def hardlink_file_list(srcpath, destpath, filelist):
    '''Hardlink every file in the path to the staging-area

    If an exception is raised, the staging-area is indeterminate.

    '''
    _process_list(srcpath, destpath, filelist, os.link)


def _copy_directories(srcdir, destdir, target):
    ''' Recursively make directories in target area and copy permissions
    '''
    dir = os.path.dirname(target)
    new_dir = os.path.join(destdir, dir)

    if not os.path.lexists(new_dir):
        if dir:
            _copy_directories(srcdir, destdir, dir)

        old_dir = os.path.join(srcdir, dir)
        if os.path.lexists(old_dir):
            dir_stat = os.lstat(old_dir)
            mode = dir_stat.st_mode

            if stat.S_ISDIR(mode):
                os.makedirs(new_dir)
                shutil.copystat(old_dir, new_dir)
            else:
                raise IOError('Source directory tree has file where '
                              'directory expected: %s' % dir)


def _process_list(srcdir, destdir, filelist, actionfunc):

    for path in sorted(filelist):
        srcpath = os.path.join(srcdir, path)
        destpath = os.path.join(destdir, path)

        # The destination directory may not have been created separately
        _copy_directories(srcdir, destdir, path)

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
            shutil.copystat(srcpath, destpath)

        elif stat.S_ISLNK(mode):
            # Copy the symlink.
            if os.path.lexists(destpath):
                os.remove(destpath)
            os.symlink(os.readlink(srcpath), destpath)

        elif stat.S_ISREG(mode):
            # Process the file.
            if os.path.lexists(destpath):
                os.remove(destpath)
            actionfunc(srcpath, destpath)

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


def make_deterministic_gztar_archive(base_name, root_dir, time=1321009871.0):
    '''Make a gzipped tar archive of contents of 'root_dir'.

    This function takes extra steps to ensure the output is deterministic,
    compared to shutil.make_archive(). First, it sorts the results of
    os.listdir() to ensure the ordering of the files in the archive is the
    same. Second, it sets a fixed timestamp and filename in the gzip header.

    As well as fixing https://bugs.python.org/issue24465, to make this function
    redundant we would need to patch shutil.make_archive() so we could manually
    set the timestamp and filename set in the gzip file header.

    '''
    # It's hard to implement this function by monkeypatching
    # shutil.make_archive() because of the way the tarfile module includes the
    # filename of the tarfile in the gzip header. So we have to reimplement
    # shutil.make_archive().

    def add_directory_to_tarfile(f_tar, dir_name, dir_arcname):
        for filename in sorted(os.listdir(dir_name)):
            name = os.path.join(dir_name, filename)
            arcname = os.path.join(dir_arcname, filename)

            f_tar.add(name=name, arcname=arcname, recursive=False)

            if os.path.isdir(name) and not os.path.islink(name):
                add_directory_to_tarfile(f_tar, name, arcname)

    with open(base_name + '.tar.gz', 'wb') as f:
        gzip_context = gzip.GzipFile(
            filename='', mode='wb', fileobj=f, mtime=time)
        with gzip_context as f_gzip:
            with tarfile.TarFile(mode='w', fileobj=f_gzip) as f_tar:
                add_directory_to_tarfile(f_tar, root_dir, '.')


def make_deterministic_tar_archive(base_name, root_dir):
    '''Make a tar archive of contents of 'root_dir'.

    This function uses monkeypatching to make shutil.make_archive() create
    a deterministic tarfile.

    https://bugs.python.org/issue24465 will make this function redundant.

    '''
    real_listdir = os.listdir

    def stable_listdir(path):
        return sorted(real_listdir(path))

    with monkeypatch(os, 'listdir', stable_listdir):
        shutil.make_archive(base_name, 'tar', root_dir)


def _find_extensions(paths):
    '''Iterate the paths, in order, finding extensions and adding them to
    the return dict.'''

    extension_kinds = ['check', 'configure', 'write']
    efs = MultiFS()
    map(lambda x: efs.addfs(x, OSFS(x)), paths)

    def get_extensions(kind):
        return {os.path.splitext(x)[0]: efs.getsyspath(x)
                for x in efs.walkfiles('.', '*.%s' % kind)}

    return {e: get_extensions(e) for e in extension_kinds}


def find_extensions():
    '''Scan definitions for extensions.'''

    paths = [app.config['extsdir']]

    return _find_extensions(paths)


def sorted_ls(path):
    mtime = lambda f: os.stat(os.path.join(path, f)).st_mtime
    return list(sorted(os.listdir(path), key=mtime))


@contextlib.contextmanager
def monkeypatch(obj, attr, new_value):
    '''Temporarily override the attribute of some object.

    For example, to override the time.time() function, so that it returns a
    fixed timestamp, you could do:

        with monkeypatch(time, 'time', lambda: 1234567):
            print time.time()

    '''
    old_value = getattr(obj, attr)
    setattr(obj, attr, new_value)
    yield
    setattr(obj, attr, old_value)
