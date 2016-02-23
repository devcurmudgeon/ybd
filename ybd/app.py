# Copyright (C) 2014-2016  Codethink Limited
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
import datetime
import os
import fcntl
import shutil
import sys
import warnings
import yaml
from multiprocessing import cpu_count
from subprocess import call, check_output
import platform
import hashlib
from repos import get_version
try:
    from riemann_client.transport import TCPTransport
    from riemann_client.client import QueuedClient
    riemann_available = True
except ImportError:
    riemann_available = False


config = {}


class Counter(object):
    def __init__(self, pid):
        self._counter_file = os.path.join(config['tmp'], str(pid))
        with open(self._counter_file, 'w') as f:
            f.write(str(0))

    def increment(self):
        with open(self._counter_file, 'r') as f:
            count = f.read()
        with open(self._counter_file, 'w') as f:
            try:
                count = int(count) + 1
                f.write(str(count))
            except:
                # FIXME work out how we can ever get here...
                pass

    def get(self):
        with open(self._counter_file, 'r') as f:
            count = f.read()
        return count


def log(component, message='', data=''):
    ''' Print a timestamped log. '''

    name = component['name'] if type(component) is dict else component

    timestamp = datetime.datetime.now().strftime('%y-%m-%d %H:%M:%S')
    if config.get('log-elapsed'):
        timestamp = timestamp[:9] + elapsed(config['start-time'])
    progress = ''
    if config.get('counter'):
        count = config['counter'].get()
        progress = '[%s/%s/%s] ' % (count, config['tasks'], config['total'])
    entry = '%s %s[%s] %s %s\n' % (timestamp, progress, name, message, data)
    if config.get('instances'):
        entry = str(config.get('fork', 0)) + ' ' + entry

    print(entry),
    sys.stdout.flush()


def log_env(log, env, message=''):
    with open(log, "a") as logfile:
        for key in sorted(env):
            msg = env[key] if 'PASSWORD' not in key else '(hidden)'
            logfile.write('%s=%s\n' % (key, msg))
        logfile.write(message + '\n\n')
        logfile.flush()


def exit(component, message, data):
    print('\n\n')
    log(component, message, data)
    print('\n\n')
    os._exit(1)


def warning_handler(message, category, filename, lineno, file=None, line=None):
    '''Output messages from warnings.warn() - default output is a bit ugly.'''

    return 'WARNING: %s\n' % (message)


def setup(args):
    if len(args) != 3:
        sys.stderr.write("Usage: %s DEFINITION_FILE ARCH\n\n" % sys.argv[0])
        sys.exit(1)

    log('SETUP', 'Running %s in' % args[0], os.getcwd())
    config['start-time'] = datetime.datetime.now()
    config['target'] = os.path.basename(os.path.splitext(args[1])[0])
    config['arch'] = args[2]
    config['sandboxes'] = []
    config['overlaps'] = []
    config['new-overlaps'] = []

    warnings.formatwarning = warning_handler
    # Suppress multiple instances of the same warning.
    warnings.simplefilter('once', append=True)

    # load config files in reverse order of precedence
    load_configs([
        os.path.join(os.getcwd(), 'ybd.conf'),
        os.path.join(os.path.dirname(__file__), '..', 'ybd.conf'),
        os.path.join(os.path.dirname(__file__), 'config', 'ybd.conf')])

    if config.get('kbas-url', 'http://foo.bar/') == 'http://foo.bar/':
        config.pop('kbas-url')
    if config.get('kbas-url'):
        if not config['kbas-url'].endswith('/'):
            config['kbas-url'] += '/'

    config['total'] = config['tasks'] = config['counter'] = 0
    config['reproduced'] = []
    config['pid'] = os.getpid()
    config['program'] = os.path.basename(args[0])
    config['my-version'] = get_version(os.path.dirname(__file__))
    config['def-version'] = get_version('.')

    config['defdir'] = os.getcwd()
    config['extsdir'] = os.path.join(config['defdir'], 'extensions')
    base_dir = os.environ.get('XDG_CACHE_HOME') or os.path.expanduser('~')
    config.setdefault('base',
                      os.path.join(base_dir, config['directories']['base']))
    for directory, path in config.get('directories', {}).items():
        try:
            if config.get(directory) is None:
                if path is None:
                    path = os.path.join(config.get('base', '/'), directory)
                config[directory] = path
            os.makedirs(config[directory])
        except OSError:
            if not os.path.isdir(config[directory]):
                exit('SETUP', 'ERROR: Can not find or create',
                     config[directory])

        log('SETUP', '%s is directory for' % config[directory], directory)

    # git replace means we can't trust that just the sha1 of a branch
    # is enough to say what it contains, so we turn it off by setting
    # the right flag in an environment variable.
    os.environ['GIT_NO_REPLACE_OBJECTS'] = '1'

    if not config.get('max-jobs'):
        config['max-jobs'] = cpu_count() / config.get('instances', 1)

    config['pid'] = os.getpid()
    config['counter'] = Counter(config['pid'])
    log('SETUP', '%s version is' % config['program'], config['my-version'])
    log('SETUP', 'Max-jobs is set to', config['max-jobs'])


def load_configs(config_files):
    for config_file in reversed(config_files):
        if os.path.exists(config_file):
            with open(config_file) as f:
                text = f.read()
            log('SETUP', 'Setting config from %s:' % config_file)
            for key, value in yaml.safe_load(text).items():
                config[key] = value
                msg = value if 'PASSWORD' not in key.upper() else '(hidden)'
                log('SETUP', '  %s=%s' % (key, msg))


def cleanup(tmpdir):
    try:
        log('SETUP', 'Trying cleanup for', tmpdir)
        with open(os.path.join(tmpdir, 'lock'), 'w') as tmp_lock:
            fcntl.flock(tmp_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            to_delete = os.listdir(tmpdir)
            fcntl.flock(tmp_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            if os.fork() == 0:
                for dirname in to_delete:
                    remove_dir(os.path.join(tmpdir, dirname))
                log('SETUP', 'Cleanup successful for', tmpdir)
                sys.exit(0)
    except IOError:
        log('SETUP', 'No cleanup for', tmpdir)


def remove_dir(tmpdir):
    if (os.path.dirname(tmpdir) == config['tmp']) and os.path.isdir(tmpdir):
        try:
            shutil.rmtree(tmpdir)
        except:
            log('SETUP', 'WARNING: unable to remove', tmpdir)


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
def timer(this, message=''):
    starttime = datetime.datetime.now()
    log(this, 'Starting ' + message)
    if type(this) is dict:
        this['start-time'] = starttime
    do_log = True
    try:
        yield
    except:
        raise
    text = '' if message == '' else ' for ' + message
    time_elapsed = elapsed(starttime)
    log(this, 'Elapsed time' + text, time_elapsed)
    log_riemann(this, 'Timer', text, time_elapsed)


def log_riemann(this, service, text, time_elapsed):
    if riemann_available and 'riemann-server' in config:
        time_split = time_elapsed.split(':')
        time_sec = int(time_split[0]) * 3600 \
            + int(time_split[1]) * 60 + int(time_split[2])
        with QueuedClient(TCPTransport(config['riemann-server'],
                                       config['riemann-port'],
                                       timeout=30)) as client:
            client.event(service=service, description=text, metric_f=time_sec)
            client.flush()


def elapsed(starttime):
    td = datetime.datetime.now() - starttime
    hours, remainder = divmod(int(td.total_seconds()), 60*60)
    minutes, seconds = divmod(remainder, 60)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def spawn():
    for fork in range(1, config.get('instances')):
        if os.fork() == 0:
            config['fork'] = fork
            log('FORKS', 'I am fork', config.get('fork'))
            break
