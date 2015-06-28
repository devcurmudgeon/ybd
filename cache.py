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

import gzip
import hashlib
import json
import os
import shutil
import sys
import tarfile
from subprocess import call

import app
import buildsystem
import repos
import utils


def cache_key(defs, this):
    definition = defs.get(this)
    if definition is None:
        app.exit(this, 'ERROR: No definition found for', this)

    if definition.get('cache'):
        return definition['cache']

    if definition.get('repo') and not definition.get('tree'):
        definition['tree'] = repos.get_tree(definition)

    hash_factors = {'arch': app.settings['arch']}

    for factor in definition.get('build-depends', []):
        hash_factors[factor] = cache_key(defs, factor)

    for factor in definition.get('contents', []):
        hash_factors[factor] = cache_key(defs, factor)

    for factor in ['tree'] + buildsystem.build_steps:
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
    app.settings['total'] += 1
    if not get_cache(defs, this):
        app.settings['tasks'] += 1
    app.log(definition, 'Cache_key is', definition['cache'])
    return definition['cache']


def make_deterministic_gztar_archive(base_name, root_dir,
                                     fixed_time=1321009871.0):
    '''Make a gzipped tar archive of contents of 'root_dir'.

    This function takes extra steps to ensure the output is deterministic,
    compared to shutil.make_archive(). First, it sorts the results of
    os.listdir() to ensure the ordering of the files in the archive is the
    same. Second, it sets a fixed timestamp and filename in the gzip header.

    As well as fixing https://bugs.python.org/issue24465, to make this function
    redundant we would need to patch shutil.make_archive() so we could manually
    set the timestamp and filename set in the gzip file header.

    '''
    # It's hard to implement this function by monkeypatching
    # shutil.make_archive() because of the way the tarfile module includes the
    # filename of the tarfile in the gzip header. So we have to reimplement
    # shutil.make_archive().

    def add_directory_to_tarfile(f_tar, dir_name, dir_arcname):
        for filename in sorted(os.listdir(dir_name)):
            name = os.path.join(dir_name, filename)
            arcname = os.path.join(dir_arcname, filename)

            f_tar.add(name=name, arcname=arcname, recursive=False)

            if os.path.isdir(name) and not os.path.islink(name):
                add_directory_to_tarfile(f_tar, name, arcname)

    with open(base_name + '.tar.gz', 'wb') as f:
        gzip_context = gzip.GzipFile(
            filename='', mode='wb', fileobj=f, mtime=fixed_time)
        with gzip_context as f_gzip:
            with tarfile.TarFile(mode='w', fileobj=f_gzip) as f_tar:
                add_directory_to_tarfile(f_tar, root_dir, '.')


def make_deterministic_tar_archive(base_name, root_dir):
    '''Make a tar archive of contents of 'root_dir'.

    This function uses monkeypatching to make shutil.make_archive() create
    a deterministic tarfile.

    https://bugs.python.org/issue24465 will make this function redundant.

    '''
    real_listdir = os.listdir

    def stable_listdir(path):
        return sorted(real_listdir(path))

    with utils.monkeypatch(os, 'listdir', stable_listdir):
        shutil.make_archive(base_name, 'tar', root_dir)


def cache(defs, this, full_root=False):
    app.log(this, "Creating cache artifact")
    cachefile = os.path.join(app.settings['artifacts'], cache_key(defs, this))
    if full_root:
        # This won't actually be deterministic, because we aren't setting a
        # uniform mtime. (I'm not sure why not).
        make_deterministic_tar_archive(cachefile, this['sandbox'])
        os.rename('%s.tar' % cachefile, cachefile)
    else:
        utils.set_mtime_recursively(this['install'])
        make_deterministic_gztar_archive(cachefile, this['install'])
        os.rename('%s.tar.gz' % cachefile, cachefile)
    app.log(this, 'Now cached as', cache_key(defs, this))
    if os.fork() == 0:
        upload(this, cachefile)
        sys.exit()


def upload(this, cachefile):
    url = app.settings['server'] + '/post'
    params = {"upfile": os.path.basename(cachefile),
              "folder": os.path.dirname(cachefile), "submit": "Submit"}
    with open(cachefile, 'rb') as local_file:
        try:
            response = requests.post(url=url, data=params,
                                     files={"file": local_file})
            app.log(this, 'Artifact uploaded')
        except:
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

    cachefile = os.path.join(app.settings['artifacts'], cache_key(defs, this))
    if os.path.exists(cachefile):
        return cachefile

    return False
