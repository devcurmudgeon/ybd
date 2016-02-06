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
from cache import cache, cache_key, get_cache, get_remote
import os
import glob
import re
import assembly
import yaml
import utils


def load_metafile(defs, target):
    '''Load an individual .meta file for a chunk or stratum

    The .meta file is expected to be in the .unpacked/baserock directory of the
    built artifact

    '''
    definition = defs.get(target)
    name = definition['name']
    cachepath, cachedir = os.path.split(get_cache(defs, target))
    metafile = os.path.join(cachepath, cachedir + '.unpacked', 'baserock', name + '.meta')
    metadata = None

    path = None
    if type(target) is str:
        path = target
    else:
        path = target['name']

    try:
        with open(metafile, "r") as f:
            metadata = yaml.safe_load(f)
    except:
        app.log(name, 'WARNING: problem loading metadata', metafile)
        return None

    if metadata:
        app.log(name, 'loaded metadata for', path)

    return metadata


def install_stratum_artifacts(defs, component, stratum, artifacts):
    '''Create the .meta files for a split stratum

    Given a stratum and a list of artifacts to split, writes new .meta files to
    the baserock dir in the 'sandbox' dir of the component and copies the files
    from the .unpacked directory of each individual chunk to the sandbox

    '''
    if os.path.exists(os.path.join(component['sandbox'], 'baserock',
                                   stratum['name'] + '.meta')):
        return

    stratum_metadata = load_metafile(defs, stratum['path'])
    split_stratum_metadata = {}
    split_stratum_metadata['products'] = []
    components = []
    for product in stratum_metadata['products']:
        for artifact in artifacts:
            if artifact == product['artifact']:
                components += product['components']
                split_stratum_metadata['products'].append(product)

    if app.config.get('log-verbose'):
        app.log(component, 'installing artifacts: ' + str(artifacts) + ' components: ' + str(components))

    baserockpath = os.path.join(component['sandbox'], 'baserock')
    if not os.path.isdir(baserockpath):
        os.mkdir(baserockpath)
    split_stratum_metafile = os.path.join(baserockpath, stratum['name'] + '.meta')
    with open(split_stratum_metafile, "w") as f:
        yaml.safe_dump(split_stratum_metadata, f, default_flow_style=False)

    cachepath, cachedir = os.path.split(get_cache(defs, stratum))
    for path in stratum['contents']:
        chunk = defs.get(path)
        if chunk.get('build-mode', 'staging') == 'bootstrap':
            continue

        metafile = os.path.join(cachepath, cachedir + '.unpacked', 'baserock', chunk['name'] + '.meta')
        try:
            with open(metafile, "r") as f:
                filelist = []
                metadata = yaml.safe_load(f)
                split_metadata = {}
                split_metadata['ref'] = metadata['ref']
                split_metadata['repo'] = metadata['repo']
                split_metadata['products'] = []
                for element in metadata['products']:
                    if element['artifact'] in components:
                        filelist += element.get('files', [])
                        split_metadata['products'].append(element)

                if split_metadata['products'] != []:
                    split_metafile = os.path.join(baserockpath, os.path.basename(metafile))
                    with open(split_metafile, "w") as f:
                        yaml.safe_dump(split_metadata, f, default_flow_style=False)

                    chunk_cachepath, chunk_cachedir = os.path.split(get_cache(defs, chunk))
                    srcpath = os.path.join(chunk_cachepath, chunk_cachedir + '.unpacked')
                    utils.copy_file_list(srcpath, component['sandbox'], filelist)
        except:
            app.log(stratum, 'WARNING: problem loading ', metafile)


def write_chunk_metafile(defs, chunk):
    '''Writes a chunk .meta file to the baserock dir of the chunk

    The split rules are used to divide up the installed files for the chunk into
    artifacts in the 'products' list

    '''
    app.log(chunk['name'], 'splitting chunk')
    metafile = os.path.join(chunk['baserockdir'], chunk['name'] + '.meta')
    metadata = {}
    metadata['repo'] = chunk.get('repo')
    metadata['ref'] = chunk.get('ref')

    install_dir = chunk['install']
    # Use both the chunk specific rules and the default rules
    split_rules = chunk.get('products', {})
    default_rules = defs.defaults.get_chunk_split_rules()

    # Compile the regexps
    regexps = []
    splits = {}
    used_dirs = {}

    def mark_used_path(path):
        while path:
            path, file = os.path.split(path)
            if path:
                used_dirs[path] = True

    for rules in split_rules, default_rules:
        for rule in rules:
            regexp = re.compile('^(?:'
                                + '|'.join(rule.get('include'))
                                + ')$')
            artifact = rule.get('artifact')
            if artifact.startswith('-'):
                artifact = chunk['name'] + artifact
            regexps.append([artifact, regexp])
            splits[artifact] = []

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
            if not path in used_dirs:
                for artifact, rule in regexps:
                    if rule.match(path) or rule.match(path + '/'):
                        splits[artifact].append(path)
                        break

    unique_artifacts = sorted(set( [a for a, r in regexps] ))
    products = [ { 'artifact': a, 'files': sorted(splits[a]) } for a in unique_artifacts ]
    metadata['products'] = products
    with app.chdir(chunk['install']), open(metafile, "w") as f:
        yaml.safe_dump(metadata, f, default_flow_style=False)


def write_stratum_metafiles(defs, stratum):
    '''Write the .meta files for a stratum to the baserock dir

    The split rules are used to divide up the installed components into artifacts
    in the 'products' list in the stratum .meta file. Each artifact contains a
    list of chunk artifacts which match the stratum splitting rules

    '''

    # Use both the stratum-specific rules and the default rules
    app.log(stratum['name'], 'splitting stratum')
    split_rules = stratum.get('products', {})
    default_rules = defs.defaults.get_stratum_split_rules()

    # Compile the regexps
    regexps = []
    splits = {}

    for rules in split_rules, default_rules:
        for rule in rules:
            regexp = re.compile('^(?:'
                                + '|'.join(rule.get('include'))
                                + ')$')
            artifact = rule.get('artifact')
            if artifact.startswith('-'):
                artifact = stratum['name'] + artifact
            regexps.append([artifact, regexp])
            splits[artifact] = []

    for item in stratum['contents']:
        chunk = defs.get(item)
        if chunk.get('build-mode', 'staging') == 'bootstrap':
            continue

        metadata = load_metafile(defs, chunk['path'])
        split_metadata = {}
        split_metadata['ref'] = metadata['ref']
        split_metadata['repo'] = metadata['repo']
        split_metadata['products'] = []

        chunk_artifacts = defs.get(chunk).get('artifacts', {})
        for artifact, target in chunk_artifacts.items():
            splits[target].append(artifact)

        for element in metadata['products']:
            for artifact, rule in regexps:
                if rule.match(element['artifact']):
                    split_metadata['products'].append(element)
                    splits[artifact].append(element['artifact'])
                    break

        split_metafile = os.path.join(stratum['baserockdir'], chunk['name'] + '.meta')
        with open(split_metafile, "w") as f:
            yaml.safe_dump(split_metadata, f, default_flow_style=False)

    metafile = os.path.join(stratum['baserockdir'], stratum['name'] + '.meta')
    metadata = {}
    products = [ { 'artifact': a, 'components': sorted(set(splits[a])) } for a, r in regexps ]
    metadata['products'] = products

    with app.chdir(stratum['install']), open(metafile, "w") as f:
        yaml.safe_dump(metadata, f, default_flow_style=False)
