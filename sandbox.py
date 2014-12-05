# Copyright (C) 2011-2014  Codethink Limited
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
import textwrap
from subprocess import call
import app

@contextlib.contextmanager
def setup(this):
    try:
        jail = app.config['assembly']
        for directory in ['dev', 'etc', 'lib', 'usr', 'bin']:
            call(['mkdir', '-p', os.path.join(jail, directory)])
        devnull = os.path.join(jail, 'dev/null')
        call(['sudo', 'mknod', devnull, 'c', '1', '3'])
        call(['sudo', 'chmod', '666', devnull])
        etcdir = os.path.join(jail, 'etc')
        call(['cp', '/etc/ld.so.cache', etcdir])
        call(['cp', '/etc/ld.so.conf', etcdir])

        yield

    finally:
        pass

@contextlib.contextmanager
def chroot(dir, env):
    print('Chrooting %s' % dir)
    try:
        yield

    finally:
        pass

def unshared_cmdline(args, root='/', mounts=()):
    '''Describe how to run 'args' inside a separate mount namespace.

    This function wraps 'args' in a rather long commandline that ensures
    the subprocess cannot see any of the system's mounts other than those
    listed in 'mounts', and mounts done by that command can only be seen
    by that subprocess and its children. When the subprocess exits all
    of its mounts will be unmounted.

    '''
    # We need to do mounts in a different namespace. Unfortunately
    # this means we have to in-line the mount commands in the
    # command-line.

    command = textwrap.dedent(r'''
    mount --make-rprivate /
    root="$1"
    shift
    ''')
    cmdargs = [root]

    # We need to mount all the specified mounts in the namespace,
    # we don't need to unmount them before exiting, as they'll be
    # unmounted when the namespace is no longer used.
    command += textwrap.dedent(r'''
    while true; do
        case "$1" in
        --)
            shift
            break
            ;;
        *)
            mount_point="$1"
            mount_type="$2"
            mount_source="$3"
            shift 3
            path="$root/$mount_point"
            mount -t "$mount_type" "$mount_source" "$path"
            ;;
        esac
    done
    ''')
    for mount_point, mount_type, source in mounts:
        path = os.path.join(root, mount_point)
        if not os.path.exists(path):
            os.makedirs(path)
        cmdargs.extend((mount_point, mount_type, source))
    cmdargs.append('--')

    command += textwrap.dedent(r'''
    exec "$@"
    ''')
    cmdargs.extend(args)

    # The single - is just a shell convention to fill $0 when using -c,
    # since ordinarily $0 contains the program name.
    cmdline = ['unshare', '--mount', '--', 'sh', '-ec', command, '-']
    cmdline.extend(cmdargs)
    return cmdline


def run_cmd(this, command):
#   call(sandbox.containerised_cmdline(args))
    app.log(this, 'running command', containerised_cmdline(command))


def containerised_cmdline(args, cwd='.', root='/', binds=(),
                          mount_proc=False, unshare_net=False,
                          writable_paths=None, **kwargs):
    '''
    Describe how to run 'args' inside a linux-user-chroot container.

    The subprocess will only be permitted to write to the paths we
    specifically allow it to write to, listed in 'writeable paths'. All
    other locations in the file system will be read-only.

    The 'binds' parameter allows mounting of arbitrary file-systems,
    such as tmpfs, before running commands, by setting it to a list of
    (mount_point, mount_type, source) triples.

    The 'root' parameter allows running the command in a chroot, allowing
    the host file system to be hidden completely except for the paths
    below 'root'.

    The 'mount_proc' flag enables mounting of /proc inside 'root'.
    Locations from the file system can be bind-mounted inside 'root' by
    setting 'binds' to a list of (src, dest) pairs. The 'dest'
    directory must be inside 'root'.

    The subprocess will be run in a separate mount namespace. It can
    optionally be run in a separate network namespace too by setting
    'unshare_net'.

    '''

    if not root.endswith('/'):
        root += '/'
    if writable_paths is None:
        writable_paths = (root,)

    cmdargs = ['linux-user-chroot', '--chdir', cwd]
    if unshare_net:
        cmdargs.append('--unshare-net')
    for src, dst in binds:
        # linux-user-chroot's mount target paths are relative to the chroot
        cmdargs.extend(('--mount-bind', src, os.path.relpath(dst, root)))
    for d in invert_paths(os.walk(root), writable_paths):
        if not os.path.islink(d):
            cmdargs.extend(('--mount-readonly', os.path.relpath(d, root)))
    if mount_proc:
        proc_target = os.path.join(root, 'proc')
        if not os.path.exists(proc_target):
            os.makedirs(proc_target)
        cmdargs.extend(('--mount-proc', 'proc'))
    cmdargs.append(root)
    cmdargs.extend(args)
    return unshared_cmdline(cmdargs, root=root, **kwargs)


def invert_paths(tree_walker, paths):
    '''List paths from `tree_walker` that are not in `paths`.

    Given a traversal of a tree and a set of paths separated by os.sep,
    return the files and directories that are not part of the set of
    paths, culling directories that do not need to be recursed into,
    if the traversal supports this.

    `tree_walker` is expected to follow similar behaviour to `os.walk()`.

    This function will remove directores from the ones listed, to avoid
    traversing into these subdirectories, if it doesn't need to.

    As such, if a directory is returned, it is implied that its contents
    are also not in the set of paths.

    If the tree walker does not support culling the traversal this way,
    such as `os.walk(root, topdown=False)`, then the contents will also
    be returned.

    The purpose for this is to list the directories that can be made
    read-only, such that it would leave everything in paths writable.

    Each path in `paths` is expected to begin with the same path as
    yielded by the tree walker.

    '''

    def normpath(path):
        if path == '.':
            return path
        path = os.path.normpath(path)
        if not os.path.isabs(path):
            path = os.path.join('.', path)
        return path

    def any_paths_are_subpath_of(prefix):
        prefix = normpath(prefix)
        norm_paths = (normpath(path) for path in paths)
        return any(path[:len(prefix)] == prefix
                   for path in norm_paths)

    def path_is_listed(path):
        return any(normpath(path) == normpath(other)
                   for other in paths)

    for dirpath, dirnames, filenames in tree_walker:

        if path_is_listed(dirpath):
            # No subpaths need to be considered
            del dirnames[:]
            del filenames[:]
        elif any_paths_are_subpath_of(dirpath):
            # Subpaths may be marked, or may not, need to leave this
            # writable, so don't yield, but we don't cull.
            pass
        else:
            # not listed as a parent or an exact match, needs to be
            # yielded, but we don't need to consider subdirs, so can cull
            yield dirpath
            del dirnames[:]
            del filenames[:]

        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)
            if path_is_listed(fullpath):
                pass
            else:
                yield fullpath
