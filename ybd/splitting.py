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
import re
import yaml
from utils import copy_file_list
from fs.osfs import OSFS


def install_split_artifacts(dn):
    '''Create the .meta files for a split system

    Given a list of artifacts to split, writes new .meta files to
    the baserock dir in dn['install'] and copies the files from the
    sandbox to the dn['install']

    '''
    all_splits = []
    for i in app.defs.defaults.get_split_rules('stratum'):
        all_splits += [i['artifact']]
    for index, content in enumerate(dn['contents']):
        for stratum, artifacts in content.items():
            if artifacts == []:
                if config.get('default-splits', []) != []:
                    for split in config.get('default-splits'):
                        artifacts += [app.defs.get(stratum)['name'] + split]
                else:
                    for split in all_splits:
                        artifacts += [os.path.basename(stratum) + split]

        dn['contents'][index] = {stratum: artifacts}

    for content in dn['contents']:
        key = content.keys()[0]
        stratum = app.defs.get(key)
        move_required_files(dn, stratum, content[key])


def move_required_files(dn, stratum, artifacts):
    log(dn, 'Installing %s artifacts' % stratum['name'], artifacts)
    stratum_metadata = get_metadata(stratum)
    split_stratum_metadata = {}
    split_stratum_metadata['products'] = []
    to_keep = []
    for product in stratum_metadata['products']:
        for artifact in artifacts:
            if artifact == product['artifact']:
                to_keep += product['components']
                split_stratum_metadata['products'].append(product)

    log(dn, 'Splitting artifacts:', artifacts, verbose=True)
    log(dn, 'Splitting components:', to_keep, verbose=True)

    baserockpath = os.path.join(dn['install'], 'baserock')
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

        try:
            metafile = path_to_metafile(chunk)
            with open(metafile, "r") as f:
                filelist = []
                metadata = yaml.safe_load(f)
                split_metadata = {'ref': metadata.get('ref'),
                                  'repo': metadata.get('repo'),
                                  'products': []}
                if config.get('artifact-version', 0) not in range(0, 1):
                    metadata['cache'] = dn.get('cache')

                for product in metadata['products']:
                    if product['artifact'] in to_keep:
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
                    log(dn, 'Splits split_metadata is\n', split_metadata,
                        verbose=True)
                    log(dn, 'Splits filelist is\n', filelist, verbose=True)
                    copy_file_list(dn['sandbox'], dn['install'], filelist)
        except:
            import traceback
            traceback.print_exc()
            exit(dn, 'ERROR: failed to install split components', '')


def check_overlaps(dn):
    if set(config['new-overlaps']) <= set(config['overlaps']):
        config['new-overlaps'] = []
        return

    overlaps_found = False
    config['new-overlaps'] = list(set(config['new-overlaps']))
    for path in config['new-overlaps']:
        log(dn, 'WARNING: overlapping path', path)
        for filename in os.listdir(dn['baserockdir']):
            with open(os.path.join(dn['baserockdir'], filename)) as f:
                for line in f:
                    if path[1:] in line:
                        log(filename, 'WARNING: overlap at', path[1:])
                        overlaps_found = True
                        break
        if config.get('check-overlaps') == 'exit':
            exit(dn, 'ERROR: overlaps found', config['new-overlaps'])
    config['overlaps'] = list(set(config['new-overlaps'] + config['overlaps']))
    config['new-overlaps'] = []


def get_metadata(dn):
    '''Load an individual .meta file

    The .meta file is expected to be in the .unpacked/baserock directory of the
    built artifact

    '''
    try:
        with open(path_to_metafile(dn), "r") as f:
            metadata = yaml.safe_load(f)
        log(dn, 'Loaded metadata', dn['path'], verbose=True)
        return metadata
    except:
        log(dn, 'WARNING: problem loading metadata', dn)
        return None


def path_to_metafile(dn):
    ''' Return the path to metadata file for dn. '''

    return os.path.join(get_cache(dn) + '.unpacked', 'baserock',
                        dn['name'] + '.meta')


def compile_rules(dn):
    regexps = []
    splits = {}
    split_rules = dn.get('products', [])
    default_rules = app.defs.defaults.get_split_rules(dn.get('kind', 'chunk'))
    for rules in split_rules, default_rules:
        for rule in rules:
            regexp = re.compile('^(?:' + '|'.join(rule.get('include')) + ')$')
            artifact = rule.get('artifact')
            if artifact.startswith('-'):
                artifact = dn['name'] + artifact
            regexps.append([artifact, regexp])
            splits[artifact] = []

    return regexps, splits


def write_metadata(dn):
    if dn.get('kind', 'chunk') == 'chunk':
        write_chunk_metafile(dn)
    elif dn.get('kind', 'chunk') == 'stratum':
        write_stratum_metafiles(dn)
    if config.get('check-overlaps', 'ignore') != 'ignore':
        check_overlaps(dn)


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

        if config.get('artifact-version', 0) not in range(0, 1):
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


def write_metafile(rules, splits, dn):
    metadata = {'products': [{'artifact': a,
                              'components': sorted(set(splits[a]))}
                             for a, r in rules]}

    if dn.get('kind', 'chunk') == 'chunk':
        metadata['repo'] = dn.get('repo')
        metadata['ref'] = dn.get('ref')
    else:
        if config.get('artifact-version', 0) not in range(0, 2):
            metadata['repo'] = config['defdir']
            metadata['ref'] = config['def-version']

    if config.get('artifact-version', 0) not in range(0, 1):
        metadata['cache'] = dn.get('cache')

    meta = os.path.join(dn['baserockdir'], dn['name'] + '.meta')

    with open(meta, "w") as f:
        yaml.safe_dump(metadata, f, default_flow_style=False)
