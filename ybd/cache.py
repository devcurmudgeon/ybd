# Copyright (C) 2014-2016 Codethink Limited
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

import requests

import hashlib
import json
import os
import shutil
from subprocess import call

import app
from repos import get_repo_url, get_tree
import utils
import tempfile
import yaml
import re


def cache_key(dn):
    if dn is None:
        app.log(dn, 'No definition found for', dn, exit=True)

    if type(dn) is not dict:
        dn = app.defs.get(dn)

    if dn.get('cache') == 'calculating':
        app.log(dn, 'Recursion loop for', dn, exit=True)

    if dn.get('cache'):
        return dn['cache']

    if dn.get('arch', app.config['arch']) != app.config['arch']:
        app.log(dn, 'Cache_key requested but arch %s mismatch' % dn['arch'],
                app.config['arch'])
        return False

    dn['cache'] = 'calculating'

    key = 'no-build'
    if app.config.get('mode', 'normal') in ['keys-only', 'normal']:
        if dn.get('repo') and not dn.get('tree'):
            dn['tree'] = get_tree(dn)
        factors = hash_factors(dn)
        factors = json.dumps(factors, sort_keys=True).encode('utf-8')
        key = hashlib.sha256(factors).hexdigest()

    dn['cache'] = dn['name'] + "." + key

    app.config['total'] += 1
    x = 'x'
    if not get_cache(dn):
        x = ' '
        app.config['tasks'] += 1

    if dn.get('kind', 'chunk') == 'chunk':
        app.config['chunks'] += 1
    if dn.get('kind', 'chunk') == 'stratum':
        app.config['strata'] += 1
    if dn.get('kind', 'chunk') == 'system':
        app.config['systems'] += 1

    app.log('CACHE-KEYS', '[%s]' % x, dn['cache'])
    if app.config.get('manifest', False):
        update_manifest(dn, app.config['manifest'])

    if 'keys' in app.config:
        app.config['keys'] += [dn['cache']]
    return dn['cache']


def hash_factors(dn):
    hash_factors = {'arch': app.config['arch']}

    for factor in dn.get('build-depends', []):
        hash_factors[factor] = cache_key(factor)

    for factor in dn.get('contents', []):
        hash_factors[factor.keys()[0]] = cache_key(factor.keys()[0])

    for factor in ['tree', 'submodules'] + app.defs.defaults.build_steps:
        if dn.get(factor):
            hash_factors[factor] = dn[factor]

    if dn.get('kind') == 'system':
        if app.config.get('default-splits', []) != []:
            hash_factors['splits'] = app.config.get('default-splits')

    def hash_system_recursively(system):
        factor = system.get('path', 'BROKEN')
        hash_factors[factor] = cache_key(factor)
        for subsystem in system.get('subsystems', []):
            hash_system_recursively(subsystem)

    if dn.get('kind') == 'cluster':
        for system in dn.get('systems', []):
            hash_system_recursively(system)

    if app.config.get('artifact-version', False):
        hash_factors['artifact-version'] = app.config.get('artifact-version')

        if app.config.get('artifact-version', 0) in range(0, 2):
            # this way, any change to any build-system invalidates all caches
            hash_factors['default-build-systems'] = \
                app.defs.defaults.build_systems
        else:
            # this way is better - only affected components get a new key
            hash_factors['default-build-systems'] = \
                app.defs.defaults.build_systems.get(dn.get('build-system',
                                                    'manual'))
            if (app.config.get('default-splits', []) != [] and
                    dn.get('kind') == 'system'):
                hash_factors['default-splits'] = app.config['default-splits']

    return hash_factors


def cache(dn):
    if get_cache(dn):
        app.log(dn, "Bah! I could have cached", cache_key(dn))
        return
    tempfile.tempdir = app.config['tmp']
    tmpdir = tempfile.mkdtemp()
    cachefile = os.path.join(tmpdir, cache_key(dn))
    if dn.get('kind') == "system":
        utils.hardlink_all_files(dn['install'], dn['sandbox'])
        shutil.rmtree(dn['checkout'])
        utils.set_mtime_recursively(dn['install'])
        utils.make_deterministic_tar_archive(cachefile, dn['install'])
        shutil.move('%s.tar' % cachefile, cachefile)
    else:
        utils.set_mtime_recursively(dn['install'])
        utils.make_fixed_gztar_archive(cachefile, dn['install'])
        shutil.move('%s.tar.gz' % cachefile, cachefile)

    app.config['counter'].increment()

    unpack(dn, cachefile)
    if app.config.get('kbas-password', 'insecure') != 'insecure' and \
            app.config.get('kbas-url') is not None:
        if dn.get('kind', 'chunk') in app.config.get('kbas-upload', 'chunk'):
            with app.timer(dn, 'upload'):
                upload(dn)


def update_manifest(dn, manifest):
    with open(manifest, "a") as m:
        if manifest.endswith('text'):
            format = '%s %s %s %s %s %s\n'
            m.write(format % (dn['name'], dn['cache'],
                              get_repo_url(dn.get('repo', 'None')),
                              dn.get('ref', 'None'),
                              dn.get('unpetrify-ref', 'None'),
                              md5(get_cache(dn))))
            m.flush()
            return

        text = {'name': dn['name'],
                'summary': {'artifact': dn['cache'],
                            'repo': get_repo_url(dn.get('repo', None)),
                            'sha': dn.get('ref', None),
                            'ref': dn.get('unpetrify-ref', None),
                            'md5': md5(get_cache(dn))}}
        m.write(yaml.dump(text, default_flow_style=True))
        m.flush()


def unpack(dn, tmpfile):
    unpackdir = tmpfile + '.unpacked'
    os.makedirs(unpackdir)
    if call(['tar', 'xf', tmpfile, '--directory', unpackdir]):
        app.log(dn, 'WARNING: Problem unpacking', tmpfile, exit=True)

    try:
        path = os.path.join(app.config['artifacts'], cache_key(dn))
        shutil.move(os.path.dirname(tmpfile), path)
        if not os.path.isdir(path):
            app.log(dn, 'Problem creating artifact', path, exit=True)

        size = os.path.getsize(get_cache(dn))
        size = re.sub("(\d)(?=(\d{3})+(?!\d))", r"\1,", "%d" % size)
        checksum = md5(get_cache(dn))
        app.log(dn, 'Cached %s bytes %s as' % (size, checksum),
                cache_key(dn))
        return path
    except:
        app.log(dn, 'Bah! I raced on', cache_key(dn))
        shutil.rmtree(os.path.dirname(tmpfile))
        return False


def upload(dn):
    cachefile = get_cache(dn)
    url = app.config['kbas-url'] + 'upload'
    params = {"filename": dn['cache'],
              "password": app.config['kbas-password'],
              "checksum": md5(cachefile)}
    with open(cachefile, 'rb') as f:
        try:
            response = requests.post(url=url, data=params, files={"file": f})
            if response.status_code == 201:
                app.log(dn, 'Uploaded %s to' % dn['cache'], url)
                return
            if response.status_code == 777:
                app.log(dn, 'Reproduced %s at' % md5(cachefile), dn['cache'])
                app.config['reproduced'].append([md5(cachefile), dn['cache']])
                return
            if response.status_code == 405:
                # server has different md5 for this artifact
                if dn['kind'] == 'stratum' and app.config['reproduce']:
                    app.log('BIT-FOR-BIT',
                            'WARNING: reproduction failed for', dn['cache'])
                app.log(dn, 'Artifact server already has', dn['cache'])
                return
            app.log(dn, 'Artifact server problem:', response.status_code)
        except:
            pass
        app.log(dn, 'Failed to upload', dn['cache'])


def get_cache(dn):
    ''' Check if a cached artifact exists for the hashed version of d. '''

    if cache_key(dn) is False:
        return False

    cachedir = os.path.join(app.config['artifacts'], cache_key(dn))
    if os.path.isdir(cachedir):
        call(['touch', cachedir])
        artifact = os.path.join(cachedir, cache_key(dn))
        unpackdir = artifact + '.unpacked'
        if not os.path.isdir(unpackdir):
            tempfile.tempdir = app.config['tmp']
            tmpdir = tempfile.mkdtemp()
            if call(['tar', 'xf', artifact, '--directory', tmpdir]):
                app.log(dn, 'Problem unpacking', artifact)
                return False
            try:
                shutil.move(tmpdir, unpackdir)
            except:
                # corner case... if we are here ybd is multi-instance, this
                # artifact was uploaded from somewhere, and more than one
                # instance is attempting to unpack. another got there first
                pass
        return os.path.join(cachedir, cache_key(dn))

    return False


def get_remote(dn):
    ''' If a remote cached artifact exists for d, retrieve it '''
    if app.config.get('last-retry-component') == dn or dn.get('tried'):
        return False

    dn['tried'] = True  # let's not keep asking for this artifact

    if dn.get('kind', 'chunk') not in app.config.get('kbas-upload', 'chunk'):
        return False

    try:
        app.log(dn, 'Try downloading', cache_key(dn))
        url = app.config['kbas-url'] + 'get/' + cache_key(dn)
        response = requests.get(url=url, stream=True)
    except:
        app.config.pop('kbas-url')
        app.log(dn, 'WARNING: remote artifact server is not working')
        return False

    if response.status_code == 200:
        try:
            tempfile.tempdir = app.config['tmp']
            tmpdir = tempfile.mkdtemp()
            cachefile = os.path.join(tmpdir, cache_key(dn))
            with open(cachefile, 'wb') as f:
                f.write(response.content)

            return unpack(dn, cachefile)

        except:
            app.log(dn, 'WARNING: failed downloading', cache_key(dn))

    return False


def cull(artifact_dir):
    tempfile.tempdir = app.config['tmp']
    deleted = 0

    def clear(deleted, artifact_dir):
        artifacts = utils.sorted_ls(artifact_dir)
        for artifact in artifacts:
            stat = os.statvfs(artifact_dir)
            free = stat.f_frsize * stat.f_bavail / 1000000000
            if free >= app.config.get('min-gigabytes', 10):
                app.log('SETUP', '%sGB is enough free space' % free)
                if deleted > 0:
                    app.log('SETUP', 'Culled %s items in' % deleted,
                            artifact_dir)
                return True
            path = os.path.join(artifact_dir, artifact)
            if os.path.exists(os.path.join(path, artifact + '.unpacked')):
                path = os.path.join(path, artifact + '.unpacked')
            if os.path.exists(path) and artifact not in app.config['keys']:
                tmpdir = tempfile.mkdtemp()
                shutil.move(path, os.path.join(tmpdir, 'to-delete'))
                app.remove_dir(tmpdir)
                deleted += 1
        return False

    # cull unpacked dirs first
    if clear(deleted, artifact_dir):
        return

    # cull artifacts
    if clear(deleted, artifact_dir):
        return

    stat = os.statvfs(artifact_dir)
    free = stat.f_frsize * stat.f_bavail / 1000000000
    if free < app.config.get('min-gigabytes', 10):
        app.log('SETUP', '%sGB is less than min-gigabytes:' % free,
                app.config.get('min-gigabytes', 10), exit=True)


def check(artifact):
    try:
        artifact = os.path.join(app.config['artifact-dir'], artifact,
                                artifact)
        checkfile = artifact + '.md5'
        if not os.path.exists(checkfile):
            checksum = md5(artifact)
            with open(checkfile, "w") as f:
                f.write(checksum)

        return(open(checkfile).read())
    except:
        return('================================')


def md5(filename):
    # From http://stackoverflow.com/questions/3431825
    # answer by http://stackoverflow.com/users/370483/quantumsoup
    hash = hashlib.md5()
    try:
        with open(filename, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash.update(chunk)
        return hash.hexdigest()
    except:
        return None
