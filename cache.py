#!/usr/bin/env python3
#
# Copyright (C) 2014  Codethink Limited
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

import os
import shutil
import app
import re
import hashlib
import json
import definitions
import repos


def cache_key(this):
    defs = definitions.Definitions()
    definition = defs.get(this)

    if defs.lookup(definition, 'tree') == []:
        definition['tree'] = repos.get_tree(definition)

    if defs.lookup(definition, 'cache') != []:
        return definition['cache']

    safename = definition['name'].replace('/', '-')
    hash_factors = {}

    for factor in ['build-depends', 'contents']:
        for it in defs.lookup(definition, factor):
            component = defs.get(it)

            if definition['name'] == component['name']:
                app.log(this, 'ERROR: recursion loop')
                raise SystemExit

            hash_factors[component['name']] = cache_key(component)

    for factor in ['tree', 'configure-commands', 'build-commands',
                   'install-commands']:

        if defs.lookup(definition, factor) != []:
            hash_factors[factor] = definition[factor]

    result = json.dumps(hash_factors, sort_keys=True).encode('utf-8')

    definition['cache'] = safename + "@" + hashlib.sha256(result).hexdigest()
    app.log(definition, 'Cache_key is', definition['cache'])
    return definition['cache']


def cache(this):
    cachefile = os.path.join(app.settings['artifacts'],
                             cache_key(this))

    shutil.make_archive(cachefile, 'gztar', this['install'])
    app.log(this, 'Now cached as', cache_key(this))


def get_cache(this):
    ''' Check if a cached artifact exists for the hashed version of this. '''

    cachefile = os.path.join(app.settings['artifacts'],
                             cache_key(this) + '.tar.gz')

    if os.path.exists(cachefile):
        return cachefile

    return False
