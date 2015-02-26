# Copyright (C) 2011-2015  Codethink Limited
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
from definitions import Definitions
import shutil
import utils
import cache
from repos import get_repo_url

@contextlib.contextmanager
def setup(this):

    currentdir = os.getcwd()
    currentenv = dict(os.environ)
    this['assembly'] = os.path.join(app.settings['assembly'], this['name'])
    this['build'] = os.path.join(this['assembly'], this['name']+ '.build')
    this['install'] = os.path.join(this['assembly'], this['name'] + '.inst')
    this['tmp'] = os.path.join(this['assembly'], 'tmp')
    for directory in ['assembly', 'build', 'install', 'tmp']:
        os.makedirs(this[directory])
    this['log'] = os.path.join(app.settings['artifacts'],
                               this['cache'] + '.build-log')

    try:
        build_env = clean_env(this)
        assembly_dir = app.settings['assembly']
#        for directory in ['dev', 'etc', 'lib', 'usr', 'bin', 'tmp']:
        for directory in ['dev', 'tmp']:
            call(['mkdir', '-p', os.path.join(assembly_dir, directory)])

        devnull = os.path.join(assembly_dir, 'dev/null')
        if not os.path.exists(devnull):
            call(['sudo', 'mknod', devnull, 'c', '1', '3'])
            call(['sudo', 'chmod', '666', devnull])

        for key, value in (currentenv.items() + build_env.items()):
            if key in build_env:
                os.environ[key] = build_env[key]
            else:
                os.environ.pop(key)

        os.chdir(app.settings['assembly'])

        yield
    finally:
        for key, value in currentenv.items():
            if value:
                os.environ[key] = value
            else:
                del os.environ[key]
        os.chdir(currentdir)

def cleanup(this):
    if this['build'] and this['install']:
        shutil.rmtree(this['build'])
        shutil.rmtree(this['install'])


def install_artifact(this, component, installdir):
    app.log(this, 'Installing %s in' % component['name'], installdir)
    unpackdir = unpack_artifact(component)
    utils.hardlink_all_files(unpackdir, installdir)


def unpack_artifact(component):
    cachefile = cache.get_cache(component)
    if cachefile:
        unpackdir = cachefile + '.unpacked'
        if not os.path.exists(unpackdir):
            os.makedirs(unpackdir)
            call(['tar', 'xf', cachefile, '--directory', unpackdir])
        return unpackdir

    app.log(component, 'Cached artifact not found')
    raise SystemExit


def run_cmd(this, command):

    argv = ['sh', '-c', command]
    use_chroot = True if this.get('build-mode') != 'bootstrap' else False
    do_not_mount_dirs = [this['build'], this['install']]

    if use_chroot:
        chroot_dir = app.settings['assembly']
        chdir = os.path.join('/', os.path.basename(this['build']))
        do_not_mount_dirs += [os.path.join(app.settings['assembly'], d)
                              for d in  ["dev", "proc", 'tmp']]
        mounts = ('dev/shm', 'tmpfs', 'none'),
    else:
        chroot_dir = '/'
        chdir = this['build']
        do_not_mount_dirs += [app.settings.get("TMPDIR", "/tmp")]
        mounts = []

    binds = get_binds(this)

    container_config = dict(
        cwd=chdir,
        root=chroot_dir,
        mounts=mounts,
        mount_proc=use_chroot,
        binds=binds,
        writable_paths=do_not_mount_dirs)

    cmd_list = utils.containerised_cmdline(argv, **container_config)

    log = os.path.join(app.settings['artifacts'], this['cache'] + '.build-log')
    with open(log, "a") as logfile:
        logfile.write("# # %s\n" % command)
    app.log_env(log, '\n'.join(cmd_list))
    with open(log, "a") as logfile:
        if call(cmd_list, stdout=logfile, stderr=logfile):
            app.log(this, 'ERROR: in directory', os.getcwd())
            app.log(this, 'ERROR: command failed:\n\n', cmd_list)
            app.log(this, 'ERROR: log file at', log)
            raise SystemExit


def get_binds(this):
    if app.settings['no-ccache']:
        binds = ()
    else:
        name = os.path.basename(get_repo_url(this))
        ccache_dir = os.path.join(app.settings['ccache_dir'], name)
        ccache_target = os.path.join(this['assembly'],
                                     os.environ['CCACHE_DIR'].lstrip('/'))
        if not os.path.isdir(ccache_dir):
            os.mkdir(ccache_dir)
        if not os.path.isdir(ccache_target):
            os.mkdir(ccache_target)
        binds = ((ccache_dir, ccache_target),)

    return binds


def clean_env(this):
    env = {}
    extra_path = []
    defs = Definitions()

    if app.settings['no-ccache']:
        ccache_path = []
    else:
        ccache_path = ['/usr/lib/ccache']
        env['CCACHE_DIR'] = '/tmp/ccache'
        env['CCACHE_EXTRAFILES'] = ':'.join(
            f for f in ('/baserock/binutils.meta',
                        '/baserock/eglibc.meta',
                        '/baserock/gcc.meta') if os.path.exists(f))
        if not app.settings.get('no-distcc'):
            env['CCACHE_PREFIX'] = 'distcc'

    prefixes = []

    for name in defs.lookup(this, 'build-depends'):
        dependency = defs.get(name)
        prefixes.append(defs.lookup(dependency, 'prefix'))
    prefixes = set(prefixes)
    for prefix in prefixes:
        if prefix:
            bin_path = os.path.join(prefix, 'bin')
            extra_path += [bin_path]

    if this.get('build-mode') == 'bootstrap':
        rel_path = extra_path + ccache_path
        full_path = [os.path.normpath(this['assembly'] + p)
                     for p in rel_path]
        path = full_path + app.settings['base-path']
        env['DESTDIR'] = this.get('install')
    else:
        path = extra_path + ccache_path + app.settings['base-path']
        env['DESTDIR'] = os.path.join('/',
                                      os.path.basename(this.get('install')))

    env['PATH'] = ':'.join(path)
    env['PREFIX'] = this.get('prefix') or '/usr'
    env['MAKEFLAGS'] = '-j%s' % (this.get('max_jobs') or
                                 app.settings['max_jobs'])
#    env['MAKEFLAGS'] = '-j1'

    env['TERM'] = 'dumb'
    env['SHELL'] = '/bin/sh'
    env['USER'] = env['USERNAME'] = env['LOGNAME'] = 'tomjon'
    env['LC_ALL'] = 'C'
    env['HOME'] = '/tmp'

    arch = app.settings['arch']
    cpu = 'i686' if arch == 'x86_32' else arch
    abi = 'eabi' if arch.startswith('arm') else ''
    env['TARGET'] = cpu + '-baserock-linux-gnu' + abi
    env['TARGET_STAGE1'] = cpu + '-bootstrap-linux-gnu' + abi
    env['MORPH_ARCH'] = arch

    return env
