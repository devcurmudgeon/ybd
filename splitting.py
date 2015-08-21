# Copyright (C) 2014-2015  Codethink Limited
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

import app
import os
import re


def do_chunk_splits(defs, this, metafile):
    app.log(this['name'], 'splitting chunk')
    install_dir = this['install']
    # Find the chunk-specific rule, otherwise use the defaults
    split_rules = this.get('products',
                           defs.defaults.get_chunk_split_rules())

    # Compile the regexps
    regexps = []
    splits = {}
    used_dirs = {}

    def mark_used_path(path):
        while path:
            path, file = os.path.split(path)
            if path:
                used_dirs[path] = True

    for rule in split_rules:
        regexp = re.compile('^(?:'
                            + '|'.join(rule.get('include'))
                            + ')$')
        artifact = rule.get('artifact')
        if artifact.startswith('-'):
            artifact = this['name'] + artifact
        regexps.append([artifact, regexp])
        # always include the metafile
        metapath = os.path.relpath(metafile, install_dir)
        splits[artifact] = [metapath]
        mark_used_path(metapath)

    for root, dirs, files in os.walk(install_dir, topdown=False):
        root = os.path.relpath(root, install_dir)
        if root == '.':
            root = ''

        for name in files:
            path = os.path.join(root, name)
            for artifact, rule in regexps:
                if rule.match(path):
                    splits[artifact].append(path)
                    mark_used_path(path)
                    break

        for name in dirs:
            path = os.path.join(root, name)
            if path not in used_dirs:
                for artifact, rule in regexps:
                    if rule.match(path) or rule.match(path + '/'):
                        splits[artifact].append(path)
                        break

    unique_artifacts = sorted(set([a for a, r in regexps]))
    return [{'artifact': a, 'files': sorted(splits[a])}
            for a in unique_artifacts]


def do_stratum_splits(defs, this):
    # Find the stratum-specific rule, otherwise use the defaults
    app.log(this['name'], 'splitting stratum')
    split_rules = this.get('products', {})
    default_rules = defs.defaults.get_stratum_split_rules()

    # Compile the regexps
    regexps = []
    splits = {}
    for rule in split_rules:
        regexp = re.compile('^(?:'
                            + '|'.join(rule.get('include'))
                            + ')$')
        artifact = rule.get('artifact')
        if artifact.startswith('-'):
            artifact = this['name'] + artifact
        regexps.append([artifact, regexp])
        splits[artifact] = []

    for rule in default_rules:
        artifact = rule.get('artifact')
        if artifact.startswith('-'):
            artifact = this['name'] + artifact
        if artifact not in splits:
            regexp = re.compile('^(?:'
                                + '|'.join(rule.get('include'))
                                + ')$')
            regexps.append([artifact, regexp])
            splits[artifact] = []

    for chunk in this['contents']:
        chunk_artifacts = defs.get(chunk).get('artifacts', {})
        for artifact, target in chunk_artifacts.items():
            splits[target].append(artifact)

    for chunk in this['contents']:
        chunk_artifacts = defs.get(chunk).get('_artifacts', {})
        for name in [a['artifact'] for a in chunk_artifacts]:
            for artifact, rule in regexps:
                if rule.match(name):
                    splits[artifact].append(name)
                    break

    return [{'artifact': a, 'chunks': sorted(set(splits[a]))}
            for a, r in regexps]
