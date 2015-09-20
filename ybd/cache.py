# Copyright (C) 2014-2015 Codethink Limited
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
import repos
import utils
import tempfile


def cache_key(defs, this):
    definition = defs.get(this)
    if definition is None:
        app.exit(this, 'ERROR: No definition found for', this)

    if definition.get('cache') == 'calculating':
        app.exit(this, 'ERROR: recursion loop for', this)

    if definition.get('cache'):
        return definition['cache']

    definition['cache'] = 'calculating'

    if definition.get('repo') and not definition.get('tree'):
        definition['tree'] = repos.get_tree(definition)

    hash_factors = {'arch': app.config['arch']}

    for factor in definition.get('build-depends', []):
        hash_factors[factor] = cache_key(defs, factor)

    for factor in definition.get('contents', []):
        hash_factors[factor] = cache_key(defs, factor)

    for factor in ['tree'] + defs.defaults.build_steps:
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

    result = json.dumps(hash_factors, sort_keys=True).encode('utf-8')

    safename = definition['name'].replace('/', '-')
    definition['cache'] = safename + "." + hashlib.sha256(result).hexdigest()
    app.config['total'] += 1
    if not get_cache(defs, this):
        app.config['tasks'] += 1
    app.log(definition, 'Cache_key is', definition['cache'])
    return definition['cache']


def cache(defs, this, full_root=False):
    if get_cache(defs, this):
        app.log(this, "Bah! I could have cached", cache_key(defs, this))
        return
    tempfile.tempdir = app.config['tmp']
    tmpdir = tempfile.mkdtemp()
    cachefile = os.path.join(tmpdir, cache_key(defs, this))
    if full_root:
        utils.hardlink_all_files(this['install'], this['sandbox'])
        shutil.rmtree(this['install'])
        shutil.rmtree(this['build'])
        utils.set_mtime_recursively(this['sandbox'])
        utils.make_deterministic_tar_archive(cachefile, this['sandbox'])
        os.rename('%s.tar' % cachefile, cachefile)
    else:
        utils.set_mtime_recursively(this['install'])
        utils.make_deterministic_gztar_archive(cachefile, this['install'])
        os.rename('%s.tar.gz' % cachefile, cachefile)

    unpack(defs, this, cachefile)

    if app.config.get('kbas-password', 'insecure') != 'insecure' and \
            app.config.get('kbas-url', 'http://foo.bar/') != 'http://foo.bar/':
        if this.get('kind') is not 'cluster':
            with app.timer(this, 'upload'):
                upload(defs, this)


def unpack(defs, this, tmpfile):
    unpackdir = tmpfile + '.unpacked'
    os.makedirs(unpackdir)
    if call(['tar', 'xf', tmpfile, '--directory', unpackdir]):
        app.exit(this, 'ERROR: Problem unpacking', tmpfile)

    try:
        path = os.path.join(app.config['artifacts'], cache_key(defs, this))
        os.rename(os.path.dirname(tmpfile), path)
        size = os.path.getsize(get_cache(defs, this))
        app.log(this, 'Now cached %s bytes as' % size, cache_key(defs, this))
        return path
    except:
        app.log(this, 'Bah! I raced on', cache_key(defs, this))
        shutil.rmtree(os.path.dirname(tmpfile))
        return False


def upload(defs, this):
    if this.get('kind', 'chunk') != 'chunk':
        return
    cachefile = get_cache(defs, this)
    url = app.config['kbas-url'] + 'upload'
    app.log(this, 'Uploading %s to' % this['cache'], url)
    params = {"filename": this['cache'],
              "password": app.config['kbas-password']}
    with open(cachefile, 'rb') as f:
        try:
            response = requests.post(url=url, data=params, files={"file": f})
            if response.status_code == 201:
                app.log(this, 'Uploaded artifact', this['cache'])
                return
            if response.status_code == 405:
                app.log(this, 'Artifact server already has', this['cache'])
                return
            app.log(this, 'Artifact server problem:', response.status_code)
        except:
            pass
        app.log(this, 'Failed to upload', this['cache'])


def get_cache(defs, this):
    ''' Check if a cached artifact exists for the hashed version of this. '''

    cachedir = os.path.join(app.config['artifacts'], cache_key(defs, this))
    if os.path.isdir(cachedir):
        artifact = os.path.join(cachedir, cache_key(defs, this))
        unpackdir = artifact + '.unpacked'
        if not os.path.isdir(unpackdir):
            tempfile.tempdir = app.config['tmp']
            tmpdir = tempfile.mkdtemp()
            if call(['tar', 'xf', artifact, '--directory', tmpdir]):
                app.exit(this, 'ERROR: Problem unpacking', artifact)
            try:
                os.rename(tmpdir, unpackdir)
            except:
                # corner case... if we are here ybd is multi-instance, this
                # artifact was uploaded from somewhere, and more than one
                # instance is attempting to unpack. another got there first
                pass
        return os.path.join(cachedir, cache_key(defs, this))

    return False


def get_remote(defs, this):
    ''' If a remote cached artifact exists for this, retrieve it '''
    if app.config.get('kbas-url', 'http://foo.bar/') == 'http://foo.bar/':
        return False

    if this.get('kind', 'chunk') != 'chunk':
        return False

    try:
        url = app.config['kbas-url'] + 'get/' + cache_key(defs, this)
        app.log(this, 'Try downloading', cache_key(defs, this))
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
