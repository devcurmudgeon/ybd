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


import sandboxlib
import contextlib
import os
import pipes
import shutil
import stat
import tempfile
from subprocess import call, PIPE

import app
import cache
from definitions import Definitions
from repos import get_repo_url
import utils


def builddir_for_component(this):
    return this['name'] + '.build'


def installdir_for_component(this):
    return this['name'] + '.inst'


@contextlib.contextmanager
def setup(this):
    currentdir = os.getcwd()
    currentenv = dict(os.environ)

    tempfile.tempdir = app.settings['staging']
    this['sandbox'] = tempfile.mkdtemp()
    this['build'] = os.path.join(
        this['sandbox'], builddir_for_component(this))
    this['install'] = os.path.join(
        this['sandbox'], installdir_for_component(this))
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

        yield

    finally:
        for key, value in currentenv.items():
            if value:
                os.environ[key] = value
            else:
                if os.environ.get(key):
                    os.environ.pop(key)


def remove(this):
    if this['sandbox'] != '/' and os.path.isdir(this['sandbox']):
        if os.fork() == 0:
            shutil.rmtree(this['sandbox'])
            app.exit(this, 'Cleaned up', this['sandbox'])


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


def argv_to_string(argv):
    return ' '.join(map(pipes.quote, argv))


def run_sandboxed(this, command, allow_parallel=False):
    app.log(this, 'Running command:\n%s' % command)
    with open(this['log'], "a") as logfile:
        logfile.write("# # %s\n" % command)

    executor = sandboxlib.linux_user_chroot
    sandbox_config = executor.maximum_possible_isolation()

    mounts = ccache_mounts(this)

    if this.get('build-mode') == 'bootstrap':
        # bootstrap mode: builds have some access to the host system, so they
        # can use the compilers etc.
        tmpdir = app.settings.get("TMPDIR", "/tmp")

        writable_paths = [
            this['build'], this['install'], tmpdir,
        ]

        sandbox_config.update(dict(
            cwd=this['build'],
            filesystem_root='/',
            filesystem_writable_paths=writable_paths,
            extra_mounts=[],
        ))
    else:
        # normal mode: builds run in a chroot with only their dependencies
        # present.

        mounts.extend([
            (None, '/dev/shm', 'tmpfs'),
            (None, '/proc', 'proc'),
        ])

        if this.get('kind') == 'system':
            writable_paths = 'all'
        else:
            writable_paths = [
                builddir_for_component(this),
                installdir_for_component(this),
                '/dev', '/proc', '/tmp',
            ]

        sandbox_config.update(dict(
            cwd=builddir_for_component(this),
            filesystem_root=this['sandbox'],
            filesystem_writable_paths=writable_paths,
            extra_mounts=mounts,
        ))

    argv = ['sh', '-c', command]

    cur_makeflags = os.environ.get("MAKEFLAGS")

    try:
        if not allow_parallel:
            os.environ.pop("MAKEFLAGS", None)

        # The setup() function modifies os.environ directly to match the build
        # environment. so there isn't any leakage of host environment
        # variables here.
        env = os.environ
        app.log_env(this['log'], argv_to_string(argv))

        with open(this['log'], "a") as logfile:
            exit_code = executor.run_sandbox_with_redirection(
                argv, stdout=logfile, stderr=sandboxlib.STDOUT,
                env=env, **sandbox_config)

        if exit_code != 0:
            app.log(this, 'ERROR: command failed in directory %s:\n\n' %
                    os.getcwd(), argv_to_string(argv))
            app.exit(this, 'ERROR: log file is at', this['log'])
    finally:
        if cur_makeflags is not None:
            os.environ["MAKEFLAGS"] = cur_makeflags


def run_logged(this, cmd_list):
    app.log_env(this['log'], argv_to_string(cmd_list))
    with open(this['log'], "a") as logfile:
        if call(cmd_list, stdin=PIPE, stdout=logfile, stderr=logfile):
            app.log(this, 'ERROR: command failed in directory %s:\n\n' %
                    os.getcwd(), argv_to_string(cmd_list))
            app.exit(this, 'ERROR: log file is at', this['log'])


def run_extension(this, deployment, step, method):
    app.log(this, 'Running %s extension:' % step, method)
    extensions = utils.find_extensions()
    tempfile.tempdir = tmp = app.settings['tmp']
    cmd_tmp = tempfile.NamedTemporaryFile(delete=False)
    cmd_bin = extensions[step][method]

    if method == 'ssh-rsync':
        envlist = ['UPGRADE=yes']
    else:
        envlist = ['UPGRADE=no']

    for key, value in deployment.iteritems():
        if key.isupper():
            envlist.append("%s=%s" % (key, value))

    command = ["env"] + envlist + [cmd_tmp.name]

    if step in ('write', 'configure'):
        command.append(this['sandbox'])

    if step in ('write', 'check'):
        command.append(deployment['location'])

    with app.chdir(app.settings['defdir']):
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


def ccache_mounts(this):
    if app.settings['no-ccache'] or 'repo' not in this:
        mounts = []
    else:
        name = os.path.basename(get_repo_url(this['repo']))

        ccache_dir = os.path.join(app.settings['ccache_dir'], name)
        if not os.path.isdir(ccache_dir):
            os.mkdir(ccache_dir)

        ccache_target = os.environ['CCACHE_DIR']

        mounts = [(ccache_dir, ccache_target, None, 'bind')]
    return mounts


def clean_env(this):
    env = {}
    extra_path = []
    defs = Definitions()
    arch_dict = {
        'i686': "x86_32",
        'armv8l64': "aarch64",
        'armv8b64': "aarch64_be"
    }

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
    env['TZ'] = 'UTC'

    arch = app.settings['arch']
    cpu = arch_dict.get(arch, arch)
    abi = 'eabi' if arch.startswith('arm') else ''
    env['TARGET'] = cpu + '-baserock-linux-gnu' + abi
    env['TARGET_STAGE1'] = cpu + '-bootstrap-linux-gnu' + abi
    env['MORPH_ARCH'] = arch
    env['DEFINITIONS_REF'] = app.settings['def-ver']
    env['YBD_REF'] = app.settings['ybd-version']

    return env


def create_devices(this):
    perms_mask = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
    for device in this['devices']:
        destfile = os.path.join(this['install'], './' + device['filename'])
        mode = int(device['permissions'], 8) & perms_mask
        if device['type'] == 'c':
            mode = mode | stat.S_IFCHR
        elif device['type'] == 'b':
            mode = mode | stat.S_IFBLK
        else:
            raise IOError('Cannot create device node %s,'
                          'unrecognized device type "%s"'
                          % (destfile, device['type']))
        app.log(this, "Creating device node", destfile)
        os.mknod(destfile, mode, os.makedev(device['major'], device['minor']))
        os.chown(destfile, device['uid'], device['gid'])
