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
from multiprocessing import cpu_count, Value, Lock
from subprocess import call
from fs.osfs import OSFS  # not used here, but we import it to check install
from repos import get_version
from cache import cache_key
try:
    from riemann_client.transport import TCPTransport
    from riemann_client.client import QueuedClient
    riemann_available = True
except ImportError:
    riemann_available = False


config = {}
defs = {}


class RetryException(Exception):
    def __init__(self, dn):
        if config.get('last-retry-dn') != dn:
            log(dn, 'Already assembling, so wait/retry', verbose=True)
        if config.get('last-retry-time'):
            wait = datetime.datetime.now() - config.get('last-retry-time')
            if wait.seconds < 1:
                with open(lockfile(dn), 'r') as l:
                    call(['flock', '--shared', '--timeout',
                          config.get('timeout', '60'), str(l.fileno())])
                log(dn, 'Finished wait loop', verbose=True)
        config['last-retry-time'] = datetime.datetime.now()
        config['last-retry-dn'] = dn
        for dirname in config['sandboxes']:
            remove_dir(dirname)
        config['sandboxes'] = []


# Code taken from Eli Bendersky's example at
# http://eli.thegreenplace.net/2012/01/04/shared-counter-with-pythons-multiprocessing
class Counter(object):
    def __init__(self, initval=0):
        self.val = Value('i', initval)
        self.lock = Lock()

    def increment(self):
        with self.lock:
            self.val.value += 1

    def get(self):
        with self.lock:
            return self.val.value


def lockfile(dn):
    return os.path.join(config['tmp'], cache_key(dn) + '.lock')


def log(dn, message='', data='', verbose=False, exit=False):
    ''' Print a timestamped log. '''

    if exit:
        print('\n\n')
        message = 'ERROR: ' + message.replace('WARNING: ', '')

    if verbose is True and config.get('log-verbose', False) is False:
        return

    name = dn['name'] if type(dn) is dict else dn

    timestamp = datetime.datetime.now().strftime('%y-%m-%d %H:%M:%S ')
    if config.get('log-timings') == 'elapsed':
        timestamp = timestamp[:9] + elapsed(config['start-time']) + ' '
    if config.get('log-timings', 'omit') == 'omit':
        timestamp = ''
    progress = ''
    if config.get('counter'):
        count = config['counter'].get()
        progress = '[%s/%s/%s] ' % (count, config['tasks'], config['total'])
    entry = '%s%s[%s] %s %s\n' % (timestamp, progress, name, message, data)
    if config.get('instances'):
        entry = str(config.get('fork', 0)) + ' ' + entry

    print(entry),
    sys.stdout.flush()

    if exit:
        print('\n\n')
        os._exit(1)


def log_env(log, env, message=''):
    with open(log, "a") as logfile:
        for key in sorted(env):
            msg = env[key] if 'PASSWORD' not in key else '(hidden)'
            logfile.write('%s=%s\n' % (key, msg))
        logfile.write(message + '\n\n')
        logfile.flush()


def warning_handler(message, category, filename, lineno, file=None, line=None):
    '''Output messages from warnings.warn() - default output is a bit ugly.'''

    return 'WARNING: %s\n' % (message)


def setup(args):
    config['start-time'] = datetime.datetime.now()
    config['program'] = os.path.basename(args[0])
    config['my-version'] = get_version(os.path.dirname(__file__))
    log('SETUP', '%s version is' % config['program'], config['my-version'])
    if len(args) != 3:
        sys.stdout.write("\nUsage: %s DEFINITION_FILE ARCH\n\n" % sys.argv[0])
        sys.exit(1)

    log('SETUP', 'Running %s in' % args[0], os.getcwd())
    config['target'] = os.path.basename(os.path.splitext(args[1])[0])
    config['arch'] = args[2]
    config['sandboxes'] = []
    config['overlaps'] = []
    config['new-overlaps'] = []

    warnings.formatwarning = warning_handler
    # Suppress multiple instances of the same warning.
    warnings.simplefilter('once', append=True)

    # dump any applicable environment variables into a config file
    with open('./ybd.environment', 'w') as f:
        for key in os.environ:
            if key[:4] == "YBD_":
                f.write(key[4:] + ": " + os.environ.get(key) + '\n')

    # load config files in reverse order of precedence
    load_configs([
        os.path.join(os.getcwd(), 'ybd.environment'),
        os.path.join(os.getcwd(), 'ybd.conf'),
        os.path.join(os.path.dirname(__file__), '..', 'ybd.conf'),
        os.path.join(os.path.dirname(__file__), 'config', 'ybd.conf')])

    if config.get('kbas-url', 'http://foo.bar/') == 'http://foo.bar/':
        config.pop('kbas-url')
    if config.get('kbas-url'):
        if not config['kbas-url'].endswith('/'):
            config['kbas-url'] += '/'

    config['total'] = config['tasks'] = config['counter'] = 0
    config['systems'] = config['strata'] = config['chunks'] = 0
    config['reproduced'] = []
    config['keys'] = []
    config['pid'] = os.getpid()
    config['def-version'] = get_version('.')

    config['defdir'] = os.getcwd()
    config['extsdir'] = os.path.join(config['defdir'], 'extensions')
    if config.get('manifest') is True:
        config['manifest'] = os.path.join(config['defdir'],
                                          os.path.basename(config['target']) +
                                          '.manifest')
        try:
            os.remove(config['manifest'])
        except OSError:
            pass

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
                log('SETUP', 'Cannot find or create', config[directory],
                    exit=True)

        log('SETUP', '%s is directory for' % config[directory], directory)

    # git replace means we can't trust that just the sha1 of a branch
    # is enough to say what it contains, so we turn it off by setting
    # the right flag in an environment variable.
    os.environ['GIT_NO_REPLACE_OBJECTS'] = '1'

    if 'max-jobs' not in config:
        config['max-jobs'] = cpu_count()

    if 'instances' not in config:
        # based on some testing (mainly on AWS), maximum effective
        # max-jobs value seems to be around 8-10 if we have enough cores
        # users should set values based on workload and build infrastructure
        # FIXME: more testing :)
        if cpu_count() >= 10:
            config['instances'] = 1 + (cpu_count() / 10)
            config['max-jobs'] = cpu_count() / config['instances']

    config['pid'] = os.getpid()
    config['counter'] = Counter()
    log('SETUP', 'Max-jobs is set to', config['max-jobs'])


def load_configs(config_files):
    for config_file in reversed(config_files):
        if os.path.exists(config_file):
            with open(config_file) as f:
                text = f.read()
                if yaml.safe_load(text) is None:
                    return
            log('SETUP', 'Setting config from %s:' % config_file)

            for key, value in yaml.safe_load(text).items():
                config[key.replace('_', '-')] = value
                msg = value if 'PASSWORD' not in key.upper() else '(hidden)'
                print '   %s=%s' % (key.replace('_', '-'), msg)
        print


def cleanup(tmpdir):
    if not config.get('cleanup', True):
        log('SETUP', 'WARNING: no cleanup for', tmpdir)
        return

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
        log('SETUP', 'WARNING: no cleanup for', tmpdir)


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
def timer(dn, message=''):
    starttime = datetime.datetime.now()
    log(dn, 'Starting ' + message)
    if type(dn) is dict:
        dn['start-time'] = starttime
    try:
        yield
    except:
        raise
    text = '' if message == '' else ' for ' + message
    time_elapsed = elapsed(starttime)
    log(dn, 'Elapsed time' + text, time_elapsed)
    log_riemann(dn, 'Timer', text, time_elapsed)


def log_riemann(dn, service, text, time_elapsed):
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
