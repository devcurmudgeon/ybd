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
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# =*= License: GPL-2 =*=

import contextlib
import os
import textwrap
from subprocess import call, PIPE, check_output
import app
from definitions import Definitions
import shutil
import utils
import cache
from repos import get_repo_url
import tempfile
import stat


@contextlib.contextmanager
def setup(this):

    currentdir = os.getcwd()
    currentenv = dict(os.environ)

    tempfile.tempdir = app.settings['staging']
    this['sandbox'] = tempfile.mkdtemp()
    this['build'] = os.path.join(this['sandbox'], this['name'] + '.build')
    this['install'] = os.path.join(this['sandbox'], this['name'] + '.inst')
    this['baserockdir'] = os.path.join(this['install'], 'baserock')
    this['tmp'] = os.path.join(this['sandbox'], 'tmp')
    for directory in ['build', 'install', 'tmp', 'baserockdir']:
        os.makedirs(this[directory])
    this['log'] = os.path.join(app.settings['artifacts'],
                               this['cache'] + '.build-log')
    try:
        build_env = clean_env(this)
        assembly_dir = this['sandbox']
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

        os.chdir(this['sandbox'])
        app.log(this, 'Sandbox is at', this['sandbox'])

        yield
    finally:
        for key, value in currentenv.items():
            if value:
                os.environ[key] = value
            else:
                if os.environ.get(key):
                    os.environ.pop(key)
        os.chdir(currentdir)


def remove(this):
    if this['sandbox'] != '/' and os.path.isdir(this['sandbox']):
        app.log(this, 'Cleaning up', this['sandbox'])
        shutil.rmtree(this['sandbox'])


def install(this, component):
    if os.path.exists(os.path.join(this['sandbox'], 'baserock',
                                   component['name'] + '.meta')):
        return

    app.log(this, 'Installing %s' % component['cache'])
    _install(this, component)


def _install(this, component):
    if os.path.exists(os.path.join(this['sandbox'], 'baserock',
                                   component['name'] + '.meta')):
        return

    for it in component.get('build-depends', []):
        dependency = Definitions().get(it)
        if (dependency.get('build-mode', 'staging') ==
                component.get('build-mode', 'staging')):
            _install(this, dependency)

    for it in component.get('contents', []):
        subcomponent = Definitions().get(it)
        if subcomponent.get('build-mode', 'staging') != 'bootstrap':
            _install(this, subcomponent)

    unpackdir = cache.unpack(component)
    if this.get('kind') is 'system':
        utils.copy_all_files(unpackdir, this['sandbox'])
    else:
        utils.hardlink_all_files(unpackdir, this['sandbox'])


def ldconfig(this):
    conf = os.path.join(this['sandbox'], 'etc', 'ld.so.conf')
    if os.path.exists(conf):
        path = os.environ['PATH']
        os.environ['PATH'] = '%s:/sbin:/usr/sbin:/usr/local/sbin' % path
        cmd_list = ['ldconfig', '-r', this['sandbox']]
        run_logged(this, cmd_list)
        os.environ['PATH'] = path
    else:
        app.log(this, 'No %s, not running ldconfig' % conf)


def run_sandboxed(this, command, allow_parallel=False):
    app.log(this, 'Running command:\n%s' % command)
    with open(this['log'], "a") as logfile:
        logfile.write("# # %s\n" % command)
    rw_root = True if this.get('kind') == 'system' else False
    use_chroot = False if this.get('build-mode') == 'bootstrap' else True
    do_not_mount_dirs = [this['build'], this['install']]

    if use_chroot:
        chroot_dir = this['sandbox']
        chdir = os.path.join('/', os.path.basename(this['build']))
        do_not_mount_dirs += [os.path.join(this['sandbox'], d)
                              for d in ["dev", "proc", 'tmp']]
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
        writable_paths=None if rw_root else do_not_mount_dirs)

    argv = ['sh', '-c', command]
    cmd_list = utils.containerised_cmdline(argv, **container_config)

    cur_makeflags = os.environ.get("MAKEFLAGS")
    try:
        if not allow_parallel:
            os.environ.pop("MAKEFLAGS", None)
        run_logged(this, cmd_list, container_config)
    finally:
        if cur_makeflags is not None:
            os.environ["MAKEFLAGS"] = cur_makeflags


def run_logged(this, cmd_list, config=''):
    app.log_env(this['log'], '\n'.join(cmd_list))
    with open(this['log'], "a") as logfile:
        if call(cmd_list, stdin=PIPE, stdout=logfile, stderr=logfile):
            app.log(this, 'ERROR: command failed in directory %s:\n\n' %
                    os.getcwd(), ' '.join(cmd_list))
            app.log(this, 'ERROR: Containerisation settings:\n\n', config)
            app.log(this, 'ERROR: Path:\n\n', os.environ['PATH'])
            app.log(this, 'ERROR: log file is at', this['log'])
            raise SystemExit


def run_extension(this, deployment, step, method):
    app.log(this, 'Running %s extension:' % step, method)

    extensions = utils.find_extensions()
    tempfile.tempdir = tmp = app.settings['tmp']
    cmd_tmp = tempfile.NamedTemporaryFile(delete=False)
    cmd_bin = extensions[step][method]

    if deployment['type'] == 'ssh-rsync':
        envlist = ['UPGRADE=yes']
    else:
        envlist = ['UPGRADE=no']

    for key, value in deployment.iteritems():
        if key.isupper():
            envlist.append("%s=%s" % (key, value))

    command = ["env"] + envlist + [cmd_tmp.name] + [this['sandbox']]

    if step == 'write':
        command += [deployment['location']]

    with app.chdir(this['sandbox']):
        try:
            with open(cmd_bin, "r") as infh:
                shutil.copyfileobj(infh, cmd_tmp)
            cmd_tmp.close()
            os.chmod(cmd_tmp.name, 0o700)

            if call(command):
                app.log(this, 'ERROR: %s extension failed:' % step, cmd_bin)
                raise SystemExit
        finally:
            os.remove(cmd_tmp.name)
    return


def get_binds(this):
    if app.settings['no-ccache']:
        binds = ()
    elif 'repo' in this:
        name = os.path.basename(get_repo_url(this['repo']))
        ccache_dir = os.path.join(app.settings['ccache_dir'], name)
        ccache_target = os.path.join(this['sandbox'],
                                     os.environ['CCACHE_DIR'].lstrip('/'))
        if not os.path.isdir(ccache_dir):
            os.mkdir(ccache_dir)
        if not os.path.isdir(ccache_target):
            os.mkdir(ccache_target)
        binds = ((ccache_dir, ccache_target),)
    else:
        binds = ()
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

    for name in this.get('build-depends', []):
        dependency = defs.get(name)
        prefixes.append(dependency.get('prefix', '/usr'))
    prefixes = set(prefixes)
    for prefix in prefixes:
        if prefix:
            bin_path = os.path.join(prefix, 'bin')
            extra_path += [bin_path]

    if this.get('build-mode') == 'bootstrap':
        rel_path = extra_path + ccache_path
        full_path = [os.path.normpath(this['sandbox'] + p)
                     for p in rel_path]
        path = full_path + app.settings['base-path']
        env['DESTDIR'] = this.get('install')
    else:
        path = extra_path + ccache_path + app.settings['base-path']
        env['DESTDIR'] = os.path.join('/',
                                      os.path.basename(this.get('install')))

    env['PATH'] = ':'.join(path)
    env['PREFIX'] = this.get('prefix') or '/usr'
    env['MAKEFLAGS'] = '-j%s' % (this.get('max-jobs') or
                                 app.settings['max-jobs'])
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


def create_devices(this):
    perms_mask = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
    for device in this['devices']:
        destfile = os.path.join(this['install'], './' + device['filename'])
        mode = int(device['permissions'], 8) & perms_mask
        if device['type'] == 'c':
            mode = mode | stat.S_IFCHR
        elif dev['type'] == 'b':
            mode = mode | stat.S_IFBLK
        else:
            raise IOError('Cannot create device node %s,'
                          'unrecognized device type "%s"'
                          % (destfile, device['type']))
        app.log(this, "Creating device node", destfile)
        os.mknod(destfile, mode, os.makedev(device['major'], device['minor']))
        os.chown(destfile, device['uid'], device['gid'])
