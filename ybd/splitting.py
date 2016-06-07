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

import app
from app import config, exit, log
from cache import get_cache
import os
import glob
import re
import assembly
import yaml
import utils
from collections import OrderedDict
from fs.osfs import OSFS


def install_split_artifacts(component, stratum, artifacts):
    '''Create the .meta files for a split stratum

    Given a stratum and a list of artifacts to split, writes new .meta files to
    the baserock dir in the 'sandbox' dir of the component and copies the files
    from the .unpacked directory of each individual chunk to the sandbox

    '''
    if os.path.exists(os.path.join(component['sandbox'], 'baserock',
                                   stratum['name'] + '.meta')):
        return

    if artifacts == []:
        default_artifacts = app.defs.defaults.get_split_rules('stratum')
        for split in config.get('default-splits', []):
            artifacts += [stratum['name'] + split]

    log(component, 'Installing %s splits' % stratum['name'], artifacts)
    stratum_metadata = get_metadata(stratum)
    split_stratum_metadata = {}
    split_stratum_metadata['products'] = []
    components = []
    for product in stratum_metadata['products']:
        for artifact in artifacts:
            if artifact == product['artifact']:
                components += product['components']
                split_stratum_metadata['products'].append(product)

    log(component, 'Splitting artifacts:', artifacts, verbose=True)
    log(component, 'Splitting components:', components, verbose=True)

    baserockpath = os.path.join(component['sandbox'], 'baserock')
    if not os.path.isdir(baserockpath):
        os.mkdir(baserockpath)
    split_stratum_metafile = os.path.join(baserockpath,
                                          stratum['name'] + '.meta')
    with open(split_stratum_metafile, "w") as f:
        yaml.safe_dump(split_stratum_metadata, f, default_flow_style=False)

    for path in stratum['contents']:
        chunk = app.defs.get(path)
        if chunk.get('build-mode', 'staging') == 'bootstrap':
            continue

        if not get_cache(chunk):
            exit(stratum, 'ERROR: artifact not found', chunk.get('name'))

        try:
            metafile = path_to_metafile(chunk)
            with open(metafile, "r") as f:
                filelist = []
                metadata = yaml.safe_load(f)
                split_metadata = {'ref': metadata.get('ref'),
                                  'repo': metadata.get('repo'),
                                  'products': []}
                if config.get('artifact-version', 0) not in [0, 1]:
                    metadata['cache'] = component.get('cache')

                for product in metadata['products']:
                    if product['artifact'] in components:
                        filelist += product.get('components', [])
                        # handle old artifacts still containing 'files'
                        filelist += product.get('files', [])

                        split_metadata['products'].append(product)

                if split_metadata['products'] != []:
                    split_metafile = os.path.join(baserockpath,
                                                  os.path.basename(metafile))
                    with open(split_metafile, "w") as f:
                        yaml.safe_dump(split_metadata, f,
                                       default_flow_style=False)

                    cachepath, cachedir = os.path.split(get_cache(chunk))
                    path = os.path.join(cachepath, cachedir + '.unpacked')
                    utils.copy_file_list(path, component['sandbox'], filelist)
        except:
            # if we got here, something has gone badly wrong parsing metadata
            # or copying files into the sandbox...
            log(stratum, 'WARNING: failed copying files from', metafile)
            log(stratum, 'WARNING: copying *all* files')
            utils.copy_all_files(path, component['sandbox'])


def check_overlaps(component):
    if set(config['new-overlaps']) <= set(config['overlaps']):
        config['new-overlaps'] = []
        return

    overlaps_found = False
    config['new-overlaps'] = list(set(config['new-overlaps']))
    for path in config['new-overlaps']:
        log(component, 'WARNING: overlapping path', path)
        for filename in os.listdir(component['baserockdir']):
            with open(os.path.join(component['baserockdir'], filename)) as f:
                for line in f:
                    if path[1:] in line:
                        log(filename, 'WARNING: overlap at', path[1:])
                        overlaps_found = True
                        break
        if config.get('check-overlaps') == 'exit':
            exit(component, 'ERROR: overlaps found', config['new-overlaps'])
    config['overlaps'] = list(set(config['new-overlaps'] + config['overlaps']))
    config['new-overlaps'] = []


def get_metadata(component):
    '''Load an individual .meta file

    The .meta file is expected to be in the .unpacked/baserock directory of the
    built artifact

    '''
    try:
        with open(path_to_metafile(component), "r") as f:
            metadata = yaml.safe_load(f)
        log(component, 'Loaded metadata', component['path'], verbose=True)
        return metadata
    except:
        log(component, 'WARNING: problem loading metadata', component)
        return None


def path_to_metafile(component):
    ''' Return the path to metadata file for component. '''

    return os.path.join(get_cache(component) + '.unpacked', 'baserock',
                        component['name'] + '.meta')


def compile_rules(component):
    regexps = []
    splits = {}
    split_rules = component.get('products', [])
    default_rules = app.defs.defaults.get_split_rules(component.get('kind',
                                                                    'chunk'))
    for rules in split_rules, default_rules:
        for rule in rules:
            regexp = re.compile('^(?:' + '|'.join(rule.get('include')) + ')$')
            artifact = rule.get('artifact')
            if artifact.startswith('-'):
                artifact = component['name'] + artifact
            regexps.append([artifact, regexp])
            splits[artifact] = []

    return regexps, splits


def write_metadata(component):
    if component.get('kind', 'chunk') == 'chunk':
        write_chunk_metafile(component)
    elif component.get('kind', 'chunk') == 'stratum':
        write_stratum_metafiles(component)
    if config.get('check-overlaps', 'ignore') != 'ignore':
        check_overlaps(component)


def write_chunk_metafile(chunk):
    '''Writes a chunk .meta file to the baserock dir of the chunk

    The split rules are used to divide up the installed files for the chunk
    into artifacts in the 'products' list

    '''
    log(chunk['name'], 'Splitting', chunk.get('kind'))
    rules, splits = compile_rules(chunk)

    install_dir = chunk['install']
    fs = OSFS(install_dir)
    files = fs.walkfiles('.', search='depth')
    dirs = fs.walkdirs('.', search='depth')

    for path in files:
        for artifact, rule in rules:
            if rule.match(path):
                splits[artifact].append(path)
                break

    all_files = [a for x in splits.values() for a in x]
    for path in dirs:
        if not any(map(lambda y: y.startswith(path),
                   all_files)) and path != '':
            for artifact, rule in rules:
                if rule.match(path) or rule.match(path + '/'):
                    splits[artifact].append(path)
                    break

    write_metafile(rules, splits, chunk)


def write_stratum_metafiles(stratum):
    '''Write the .meta files for a stratum to the baserock dir

    The split rules are used to divide up the installed components into
    artifacts in the 'products' list in the stratum .meta file. Each artifact
    contains a list of chunk artifacts which match the stratum splitting rules

    '''

    log(stratum['name'], 'Splitting', stratum.get('kind'))
    rules, splits = compile_rules(stratum)

    for item in stratum['contents']:
        chunk = app.defs.get(item)
        if chunk.get('build-mode', 'staging') == 'bootstrap':
            continue

        metadata = get_metadata(chunk)
        split_metadata = {'ref': metadata.get('ref'),
                          'repo': metadata.get('repo'),
                          'products': []}

        if config.get('artifact-version', 0) not in [0, 1]:
            split_metadata['cache'] = metadata.get('cache')

        chunk_artifacts = app.defs.get(chunk).get('artifacts', {})
        for artifact, target in chunk_artifacts.items():
            splits[target].append(artifact)

        for product in metadata['products']:
            for artifact, rule in rules:
                if rule.match(product['artifact']):
                    split_metadata['products'].append(product)
                    splits[artifact].append(product['artifact'])
                    break

        meta = os.path.join(stratum['baserockdir'], chunk['name'] + '.meta')

        with open(meta, "w") as f:
            yaml.safe_dump(split_metadata, f, default_flow_style=False)

    write_metafile(rules, splits, stratum)


def write_metafile(rules, splits, component):
    metadata = {'products': [{'artifact': a,
                              'components': sorted(set(splits[a]))}
                             for a, r in rules]}

    if component.get('kind', 'chunk') == 'chunk':
        metadata['repo'] = component.get('repo')
        metadata['ref'] = component.get('ref')
    else:
        if config.get('artifact-version', 0) not in [0, 1, 2]:
            metadata['repo'] = config['defdir']
            metadata['ref'] = config['def-version']

    if config.get('artifact-version', 0) not in [0, 1]:
        metadata['cache'] = component.get('cache')

    meta = os.path.join(component['baserockdir'], component['name'] + '.meta')

    with open(meta, "w") as f:
        yaml.safe_dump(metadata, f, default_flow_style=False)
