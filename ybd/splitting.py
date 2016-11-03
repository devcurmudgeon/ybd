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

from ybd import app, config
from ybd.cache import get_cache
import os
import re
import yaml
from ybd.utils import chdir, copy_file_list, log


def install_split_artifacts(dn):
    '''Create the .meta files for a split system

    Given a list of artifacts to split, writes new .meta files to
    the baserock dir in dn['install'] and copies the files from the
    sandbox to the dn['install']

    '''
    for content in dn['contents']:
        key = list(content.keys())[0]
        stratum = config.defs.get(key)
        move_required_files(dn, stratum, content[key])


def move_required_files(dn, stratum, artifacts):
    stratum_metadata = get_metadata(stratum)
    split_stratum_metadata = {}
    if not artifacts:
        # Include all artifacts if no ones were explicitly given for an
        # included stratum on a system.
        artifacts = [p['artifact'] for p in stratum_metadata['products']]

    to_keep = [component
               for product in stratum_metadata['products']
               for component in product['components']
               if product['artifact'] in artifacts]

    split_stratum_metadata['products'] = (
              [product
               for product in stratum_metadata['products']
               if product['artifact'] in artifacts])

    log(dn, 'Installing %s artifacts' % stratum['name'], artifacts)
    log(dn, 'Installing components:', to_keep, verbose=True)

    baserockpath = os.path.join(dn['install'], 'baserock')
    if not os.path.isdir(baserockpath):
        os.mkdir(baserockpath)
    split_stratum_metafile = os.path.join(baserockpath,
                                          stratum['name'] + '.meta')
    with open(split_stratum_metafile, "w") as f:
        yaml.safe_dump(split_stratum_metadata, f, default_flow_style=False)

    for path in stratum['contents']:
        chunk = config.defs.get(path)
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
                if config.config.get('artifact-version', 0) not in range(0, 1):
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
            log(dn, 'Failed to install split components', exit=True)


def check_overlaps(dn):
    if set(config.config['new-overlaps']) <= set(config.config['overlaps']):
        config.config['new-overlaps'] = []
        return

    overlaps_found = False
    config.config['new-overlaps'] = list(set(config.config['new-overlaps']))
    for path in config.config['new-overlaps']:
        log(dn, 'WARNING: overlapping path', path)
        for filename in os.listdir(dn['baserockdir']):
            with open(os.path.join(dn['baserockdir'], filename)) as f:
                for line in f:
                    if path[1:] in line:
                        log(filename, 'WARNING: overlap at', path[1:])
                        overlaps_found = True
                        break
        if config.config.get('check-overlaps') == 'exit':
            log(dn, 'Overlaps found', config.config['new-overlaps'], exit=True)
    config.config['overlaps'] = list(set(config.config['new-overlaps'] +
                                         config.config['overlaps']))
    config.config['new-overlaps'] = []


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
    default_rules = config.defs.defaults.get_split_rules(
                        dn.get('kind', 'chunk'))
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
    if config.config.get('check-overlaps', 'ignore') != 'ignore':
        check_overlaps(dn)


def write_chunk_metafile(chunk):
    '''Writes a chunk .meta file to the baserock dir of the chunk

    The split rules are used to divide up the installed files for the chunk
    into artifacts in the 'products' list

    '''
    log(chunk['name'], 'Splitting', chunk.get('kind'))
    rules, splits = compile_rules(chunk)

    with chdir(chunk['install']):
        for root, dirs, files in os.walk('.', topdown=False):
            for name in files + dirs:
                path = os.path.join(root, name)[2:]
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
        chunk = config.defs.get(item)
        if chunk.get('build-mode', 'staging') == 'bootstrap':
            continue

        metadata = get_metadata(chunk)
        split_metadata = {'ref': metadata.get('ref'),
                          'repo': metadata.get('repo'),
                          'products': []}

        if config.config.get('artifact-version', 0) not in range(0, 1):
            split_metadata['cache'] = metadata.get('cache')

        chunk_artifacts = config.defs.get(chunk).get('artifacts', {})
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
        if config.config.get('artifact-version', 0) not in range(0, 2):
            metadata['repo'] = config.config['defdir']
            metadata['ref'] = config.config['def-version']

    if config.config.get('artifact-version', 0) not in range(0, 1):
        metadata['cache'] = dn.get('cache')

    meta = os.path.join(dn['baserockdir'], dn['name'] + '.meta')

    with open(meta, "w") as f:
        yaml.safe_dump(metadata, f, default_flow_style=False)
