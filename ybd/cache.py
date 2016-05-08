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
import sys
from subprocess import call

import app
from repos import get_repo_url, get_tree
import utils
import tempfile
import yaml


def cache_key(defs, this):
    definition = defs.get(this)
    if definition is None:
        app.exit(this, 'ERROR: No definition found for', this)

    if definition.get('cache') == 'calculating':
        app.exit(this, 'ERROR: recursion loop for', this)

    if definition.get('cache'):
        return definition['cache']

    if definition.get('arch', app.config['arch']) != app.config['arch']:
        return False

    definition['cache'] = 'calculating'

    if app.config.get('mode', 'normal') in ['parse-only', 'no-build']:
        key = 'no-build'
    else:
        if definition.get('repo') and not definition.get('tree'):
            definition['tree'] = get_tree(definition)
        factors = hash_factors(defs, definition)
        factors = json.dumps(factors, sort_keys=True).encode('utf-8')
        key = hashlib.sha256(factors).hexdigest()

    definition['cache'] = definition['name'] + "." + key

    app.config['total'] += 1
    x = 'x'
    if not get_cache(defs, this):
        x = ' '
        app.config['tasks'] += 1

    app.log(definition,'Cache_key is %s' % definition['cache'], '[' + x + ']')
    if app.config.get('manifest', False):
        update_manifest(defs, this, app.config['manifest'])

    if 'keys' in app.config:
        app.config['keys'] += [definition['cache']]
    return definition['cache']


def hash_factors(defs, definition):
    hash_factors = {'arch': app.config['arch']}

    for factor in definition.get('build-depends', []):
        hash_factors[factor] = cache_key(defs, factor)

    for factor in definition.get('contents', []):
        hash_factors[factor] = cache_key(defs, factor)

    for factor in ['tree', 'submodules'] + defs.defaults.build_steps:
        if definition.get(factor):
            hash_factors[factor] = definition[factor]

    def hash_system_recursively(system):
        factor = system.get('path', 'BROKEN')
        hash_factors[factor] = cache_key(defs, factor)
        for subsystem in system.get('subsystems', []):
            hash_system_recursively(subsystem)

    if definition.get('kind') == 'cluster':
        for system in definition.get('systems', []):
            hash_system_recursively(system)

    if app.config.get('artifact-version', False):
        hash_factors['artifact-version'] = app.config.get('artifact-version')

        if app.config.get('artifact-version', 0) in [0, 1, 2]:
            # this way, any change to any build-system invalidates all caches
            hash_factors['default-build-systems'] = defs.defaults.build_systems
        else:
            # this way is better - only affected components get a new key
            hash_factors['default-build-systems'] = \
                defs.defaults.build_systems.get(definition.get('build-system',
                                                               'manual'))

    return hash_factors


def cache(defs, this):
    if get_cache(defs, this):
        app.log(this, "Bah! I could have cached", cache_key(defs, this))
        return
    tempfile.tempdir = app.config['tmp']
    tmpdir = tempfile.mkdtemp()
    cachefile = os.path.join(tmpdir, cache_key(defs, this))
    if this.get('kind') == "system":
        utils.hardlink_all_files(this['install'], this['sandbox'])
        shutil.rmtree(this['install'])
        shutil.rmtree(this['build'])
        utils.set_mtime_recursively(this['sandbox'])
        utils.make_deterministic_tar_archive(cachefile, this['sandbox'])
        shutil.move('%s.tar' % cachefile, cachefile)
    else:
        utils.set_mtime_recursively(this['install'])
        utils.make_deterministic_gztar_archive(cachefile, this['install'])
        shutil.move('%s.tar.gz' % cachefile, cachefile)

    app.config['counter'].increment()

    unpack(defs, this, cachefile)
    if app.config.get('kbas-password', 'insecure') != 'insecure' and \
            app.config.get('kbas-url') is not None:
        if this.get('kind', 'chunk') in ['chunk', 'stratum']:
            with app.timer(this, 'upload'):
                upload(defs, this)


def update_manifest(defs, this, manifest):
    this = defs.get(this)
    with open(manifest, "a") as m:
        if manifest.endswith('text'):
            format = '%s %s %s %s %s %s\n'
            m.write(format % (this['name'], this['cache'],
                              get_repo_url(this.get('repo', 'None')),
                              this.get('ref', 'None'),
                              this.get('unpetrify-ref', 'None'),
                              md5(get_cache(defs, this))))
            m.flush()
            return

        text = {'name': this['name'],
                'summary': {'artifact': this['cache'],
                            'repo': get_repo_url(this.get('repo', None)),
                            'sha': this.get('ref', None),
                            'ref': this.get('unpetrify-ref', None),
                            'md5': md5(get_cache(defs, this))}}
        m.write(yaml.dump(text, default_flow_style=True))
        m.flush()


def unpack(defs, this, tmpfile):
    unpackdir = tmpfile + '.unpacked'
    os.makedirs(unpackdir)
    if call(['tar', 'xf', tmpfile, '--directory', unpackdir]):
        app.log(this, 'Problem unpacking', tmpfile)
        shutil.rmtree(os.path.dirname(tmpfile))
        return False

    try:
        path = os.path.join(app.config['artifacts'], cache_key(defs, this))
        shutil.move(os.path.dirname(tmpfile), path)
        if not os.path.isdir(path):
            app.exit(this, 'ERROR: problem creating cache artifact', path)

        size = os.path.getsize(get_cache(defs, this))
        checksum = md5(get_cache(defs, this))
        app.log(this, 'Cached %s bytes %s as' % (size, checksum),
                cache_key(defs, this))
        return path
    except:
        app.log(this, 'Bah! I raced on', cache_key(defs, this))
        shutil.rmtree(os.path.dirname(tmpfile))
        return False


def upload(defs, this):
    cachefile = get_cache(defs, this)
    url = app.config['kbas-url'] + 'upload'
    params = {"filename": this['cache'],
              "password": app.config['kbas-password'],
              "checksum": md5(cachefile)}
    with open(cachefile, 'rb') as f:
        try:
            response = requests.post(url=url, data=params, files={"file": f})
            if response.status_code == 201:
                app.log(this, 'Uploaded %s to' % this['cache'], url)
                return
            if response.status_code == 777:
                app.log(this, 'Reproduced %s at' % md5(cachefile),
                        this['cache'])
                app.config['reproduced'].append([md5(cachefile),
                                                 this['cache']])
                return
            if response.status_code == 405:
                # server has different md5 for this artifact
                if this['kind'] == 'stratum' and app.config['reproduce']:
                    app.log('BIT-FOR-BIT',
                            'WARNING: reproduction failed for',
                            this['cache'])
                app.log(this, 'Artifact server already has', this['cache'])
                return
            app.log(this, 'Artifact server problem:', response.status_code)
        except:
            pass
        app.log(this, 'Failed to upload', this['cache'])


def get_cache(defs, this):
    ''' Check if a cached artifact exists for the hashed version of this. '''

    if cache_key(defs, this) is False:
        return False

    cachedir = os.path.join(app.config['artifacts'], cache_key(defs, this))
    if os.path.isdir(cachedir):
        call(['touch', cachedir])
        artifact = os.path.join(cachedir, cache_key(defs, this))
        unpackdir = artifact + '.unpacked'
        if not os.path.isdir(unpackdir):
            tempfile.tempdir = app.config['tmp']
            tmpdir = tempfile.mkdtemp()
            if call(['tar', 'xf', artifact, '--directory', tmpdir]):
                app.log(this, 'Problem unpacking', artifact)
                return False
            try:
                shutil.move(tmpdir, unpackdir)
            except:
                # corner case... if we are here ybd is multi-instance, this
                # artifact was uploaded from somewhere, and more than one
                # instance is attempting to unpack. another got there first
                pass
        return os.path.join(cachedir, cache_key(defs, this))

    return False


def get_remote(defs, this):
    ''' If a remote cached artifact exists for this, retrieve it '''
    if app.config.get('last-retry-component') == this or this.get('tried'):
        return False

    if this.get('kind', 'chunk') != 'chunk':
        return False

    try:
        this['tried'] = True  # let's not keep asking for this artifact
        app.log(this, 'Try downloading', cache_key(defs, this))
        url = app.config['kbas-url'] + 'get/' + cache_key(defs, this)
        response = requests.get(url=url, stream=True)
    except:
        app.config.pop('kbas-url')
        app.log(this, 'WARNING: remote artifact server is not working')
        return False

    if response.status_code == 200:
        try:
            tempfile.tempdir = app.config['tmp']
            tmpdir = tempfile.mkdtemp()
            cachefile = os.path.join(tmpdir, cache_key(defs, this))
            with open(cachefile, 'wb') as f:
                shutil.copyfileobj(response.raw, f)

            return unpack(defs, this, cachefile)

        except:
            app.log(this, 'WARNING: failed downloading', cache_key(defs, this))

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
        app.exit('SETUP', 'ERROR: %sGB is less than min-gigabytes:' % free,
                 app.config.get('min-gigabytes', 10))


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
