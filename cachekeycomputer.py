# Copyright (C) 2012-2014  Codethink Limited
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


import hashlib
import logging

import morphlib


class CacheKeyComputer(object):

    def __init__(self, build_env):
        self._build_env = build_env
        self._calculated = {}
        self._hashed = {}

    def _filterenv(self, env):
        keys = ["LOGNAME", "MORPH_ARCH", "TARGET", "TARGET_STAGE1",
                "USER", "USERNAME"]
        return dict([(k, env[k]) for k in keys])

    def compute_key(self, source):
        try:
            return self._hashed[source]
        except KeyError:
            ret = self._hash_id(self.get_cache_id(source))
            self._hashed[source] = ret
            logging.debug(
                'computed cache key %s for artifact %s from source ',
                 ret, (source.repo_name, source.sha1, source.filename))
            return ret

    def _hash_id(self, cache_id):
        sha = hashlib.sha256()
        self._hash_dict(sha, cache_id)
        return sha.hexdigest()

    def _hash_thing(self, sha, thing):
        if type(thing) == dict:
            self._hash_dict(sha, thing)
        elif type(thing) == list:
            self._hash_list(sha, thing)
        elif type(thing) == tuple:
            self._hash_tuple(sha, thing)
        else:
            sha.update(str(thing))

    def _hash_dict(self, sha, d):
        for tup in sorted(d.iteritems()):
            self._hash_thing(sha, tup)

    def _hash_list(self, sha, l):
        for item in l:
            self._hash_thing(sha, item)

    def _hash_tuple(self, sha, tup):
        for item in tup:
            self._hash_thing(sha, item)

    def get_cache_id(self, source):
        try:
            ret = self._calculated[source]
            return ret
        except KeyError:
            cacheid = self._calculate(source)
            self._calculated[source] = cacheid
            return cacheid

    def _calculate(self, source):
        keys = {
            'env': self._filterenv(self._build_env.env),
            'kids': [{'artifact': a.name,
                      'cache-key': self.compute_key(a.source)}
                     for a in source.dependencies],
            'metadata-version': 1
        }

        morphology = source.morphology
        kind = morphology['kind']
        if kind == 'chunk':
            keys['build-mode'] = source.build_mode
            keys['prefix'] = source.prefix
            keys['tree'] = source.tree
            keys['split-rules'] = [(a, [rgx.pattern for rgx in r._regexes])
                                   for (a, r) in source.split_rules]

            # Include morphology contents, since it doesn't always come
            # from the source tree
            keys['devices'] = morphology.get('devices')
            keys['max-jobs'] = morphology.get('max-jobs')
            keys['system-integration'] = morphology.get('system-integration',
                                                        {})
            # products is omitted as they are part of the split-rules
            # include {pre-,,post-}{configure,build,test,install}-commands
            # in morphology key
            for prefix in ('pre-', '', 'post-'):
                for cmdtype in ('configure', 'build', 'test', 'install'):
                    cmd_field = prefix + cmdtype + '-commands'
                    keys[cmd_field] = morphology[cmd_field]
        elif kind in ('system', 'stratum'):
            morph_dict = dict((k, morphology[k]) for k in morphology.keys())

            # Disregard all fields of a morphology that aren't important
            ignored_fields = (
                'description', # purely cosmetic, doesn't change builds
                # The following are used to determine dependencies,
                # so are already handled by the 'kids' field.
                'strata', 'build-depends', 'chunks',
                'products')
            for key in morph_dict:
                if key not in ignored_fields:
                    keys[key] = morph_dict[key]
        if kind == 'stratum':
            keys['stratum-format-version'] = 1
        elif kind == 'system':
            keys['system-compatibility-version'] = "2~ (upgradable, root rw)"

        return keys
