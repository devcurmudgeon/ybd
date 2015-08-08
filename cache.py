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
        utils.set_mtime_recursively(this['sandbox'])
        utils.make_deterministic_tar_archive(cachefile, this['sandbox'])
        os.rename('%s.tar' % cachefile, cachefile)
    else:
        utils.set_mtime_recursively(this['install'])
        utils.make_deterministic_gztar_archive(cachefile, this['install'])
        os.rename('%s.tar.gz' % cachefile, cachefile)

    try:
        target = os.path.join(app.config['artifacts'], cache_key(defs, this))
        os.rename(tmpdir, target)
        size = os.path.getsize(get_cache(defs, this))
        app.log(this, 'Now cached %s bytes as' % size, cache_key(defs, this))
    except:
        app.log(this, 'Bah! I raced and rebuilt', cache_key(defs, this))

#    upload(this, os.path.join(target, cache_key(defs, this)))


def upload(this, cachefile):
    url = app.config['server'] + '/post'
    params = {"upfile": os.path.basename(cachefile),
              "folder": os.path.dirname(cachefile), "submit": "Submit"}
    with open(cachefile, 'rb') as local_file:
        try:
            response = requests.post(url=url, data=params,
                                     files={"file": local_file})
            app.log(this, 'Uploaded artifact', cachefile)
        except:
            app.log(this, 'Failed to upload', cachefile)
            pass


def unpack(defs, this):
    cachefile = get_cache(defs, this)
    if cachefile:
        unpackdir = cachefile + '.unpacked'
        if not os.path.exists(unpackdir):
            os.makedirs(unpackdir)
            if call(['tar', 'xf', cachefile, '--directory', unpackdir]):
                app.exit(this, 'ERROR: Problem unpacking', cachefile)
        return unpackdir

    app.exit(this, 'ERROR: Cached artifact not found', cache_key(defs, this))


def get_cache(defs, this):
    ''' Check if a cached artifact exists for the hashed version of this. '''

    cachedir = os.path.join(app.config['artifacts'], cache_key(defs, this))
    if os.path.isdir(cachedir):
        return os.path.join(cachedir, cache_key(defs, this))

    return False
