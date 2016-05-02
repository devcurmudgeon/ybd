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
from cache import get_cache
import os
import glob
import re
import assembly
import yaml
import utils
from collections import OrderedDict
from fs.osfs import OSFS


def install_stratum_artifacts(defs, component, stratum, artifacts):
    '''Create the .meta files for a split stratum

    Given a stratum and a list of artifacts to split, writes new .meta files to
    the baserock dir in the 'sandbox' dir of the component and copies the files
    from the .unpacked directory of each individual chunk to the sandbox

    '''
    if os.path.exists(os.path.join(component['sandbox'], 'baserock',
                                   stratum['name'] + '.meta')):
        return

    stratum_metadata = get_metadata(defs, stratum)
    split_stratum_metadata = {}
    split_stratum_metadata['products'] = []
    components = []
    for product in stratum_metadata['products']:
        for artifact in artifacts:
            if artifact == product['artifact']:
                components += product['components']
                split_stratum_metadata['products'].append(product)

    if app.config.get('log-verbose'):
        app.log(component, 'Installing artifacts: ' + str(artifacts) +
                ' components: ' + str(components))

    baserockpath = os.path.join(component['sandbox'], 'baserock')
    if not os.path.isdir(baserockpath):
        os.mkdir(baserockpath)
    split_stratum_metafile = os.path.join(baserockpath,
                                          stratum['name'] + '.meta')
    with open(split_stratum_metafile, "w") as f:
        yaml.safe_dump(split_stratum_metadata, f, default_flow_style=False)

    for path in stratum['contents']:
        chunk = defs.get(path)
        if not get_cache(defs, chunk):
            app.exit(stratum, 'ERROR: no cache-key for', chunk.get('name'))

        if chunk.get('build-mode', 'staging') == 'bootstrap':
            continue

        metafile = os.path.join(get_cache(defs, chunk) + '.unpacked',
                                'baserock', chunk['name'] + '.meta')
        try:
            with open(metafile, "r") as f:
                filelist = []
                metadata = yaml.safe_load(f)
                split_metadata = {'cache': metadata.get('cache'),
                                  'ref': metadata.get('ref'),
                                  'repo': metadata.get('repo'),
                                  'products': []}
                for element in metadata['products']:
                    if element['artifact'] in components:
                        filelist += element.get('files', [])
                        split_metadata['products'].append(element)

                if split_metadata['products'] != []:
                    split_metafile = os.path.join(baserockpath,
                                                  os.path.basename(metafile))
                    with open(split_metafile, "w") as f:
                        yaml.safe_dump(split_metadata, f,
                                       default_flow_style=False)

                    cachepath, cachedir = os.path.split(get_cache(defs, chunk))
                    path = os.path.join(cachepath, cachedir + '.unpacked')
                    utils.copy_file_list(path, component['sandbox'], filelist)
        except:
            # if we got here, something has gone badly wrong parsing metadata
            # or copying files into the sandbox...
            if app.config.get('artifact-version', 0) not in [0, 1]:
                import traceback
                traceback.print_exc()
                app.log(stratum, 'ERROR: failed copying files from', metafile)
                app.exit(stratum, 'ERROR: sandbox debris is at',
                         component['sandbox'])
            # FIXME... test on old artifacts... how can continuing ever work?
            app.log(stratum, 'WARNING: problem loading', metafile)
            app.log(stratum, 'WARNING: files were not copied')


def check_overlaps(defs, component):
    if set(app.config['new-overlaps']) <= set(app.config['overlaps']):
        app.config['new-overlaps'] = []
        return

    overlaps_found = False
    app.config['new-overlaps'] = list(set(app.config['new-overlaps']))
    for path in app.config['new-overlaps']:
        app.log(component, 'WARNING: overlapping path', path)
        for filename in os.listdir(component['baserockdir']):
            with open(os.path.join(component['baserockdir'], filename)) as f:
                for line in f:
                    if path[1:] in line:
                        app.log(filename, 'WARNING: overlap at', path[1:])
                        overlaps_found = True
                        break
        if app.config.get('check-overlaps') == 'exit':
            app.exit(component, 'ERROR: overlaps found',
                     app.config['new-overlaps'])
    app.config['overlaps'] = list(set(app.config['new-overlaps'] +
                                      app.config['overlaps']))
    app.config['new-overlaps'] = []


def get_metadata(defs, this):
    '''Load an individual .meta file

    The .meta file is expected to be in the .unpacked/baserock directory of the
    built artifact

    '''
    try:
        with open(get_metafile(defs, this), "r") as f:
            metadata = yaml.safe_load(f)
        if app.config.get('log-verbose'):
            app.log(this, 'Loaded metadata for', this['path'])
        return metadata
    except:
        app.log(this, 'WARNING: problem loading metadata', this)
        return None


def write_metadata(defs, component):
    kind = component.get('kind', 'chunk')
    if kind == 'chunk':
        write_chunk_metafile(defs, component)
    elif kind == 'stratum':
        write_stratum_metafiles(defs, component)
    if app.config.get('check-overlaps', 'ignore') != 'ignore':
        check_overlaps(defs, component)


def get_metafile(defs, this):
    ''' Return the path to metadata file for this. '''

    this = defs.get(this)
    return os.path.join(get_cache(defs, this) + '.unpacked', 'baserock',
                        this['name'] + '.meta')


def compile_rules(defs, component):
    regexps = []
    splits = {}
    split_rules = component.get('products', [])
    default_rules = defs.defaults.get_split_rules(component.get('kind',
                                                                'chunk'))
    for rules in split_rules, default_rules:
        for rule in rules:
            regexp = re.compile('^(?:' +
                                '|'.join(rule.get('include')) +
                                ')$')
            artifact = rule.get('artifact')
            if artifact.startswith('-'):
                artifact = component['name'] + artifact
            regexps.append([artifact, regexp])
            splits[artifact] = []

    return regexps, splits


def write_chunk_metafile(defs, chunk):
    '''Writes a chunk .meta file to the baserock dir of the chunk

    The split rules are used to divide up the installed files for the chunk
    into artifacts in the 'products' list

    '''
    app.log(chunk['name'], 'Splitting chunk')
    rules, splits = compile_rules(defs, chunk)

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


def write_stratum_metafiles(defs, stratum):
    '''Write the .meta files for a stratum to the baserock dir

    The split rules are used to divide up the installed components into
    artifacts in the 'products' list in the stratum .meta file. Each artifact
    contains a list of chunk artifacts which match the stratum splitting rules

    '''

    app.log(stratum['name'], 'Splitting stratum')
    rules, splits = compile_rules(defs, stratum)

    for item in stratum['contents']:
        chunk = defs.get(item)
        if chunk.get('build-mode', 'staging') == 'bootstrap':
            continue

        metadata = get_metadata(defs, chunk)
        split_metadata = {'cache': metadata.get('cache'),
                          'ref': metadata.get('ref'),
                          'repo': metadata.get('repo'),
                          'products': []}

        chunk_artifacts = defs.get(chunk).get('artifacts', {})
        for artifact, target in chunk_artifacts.items():
            splits[target].append(artifact)

        for element in metadata['products']:
            for artifact, rule in rules:
                if rule.match(element['artifact']):
                    split_metadata['products'].append(element)
                    splits[artifact].append(element['artifact'])
                    break

        split_metafile = os.path.join(stratum['baserockdir'],
                                      chunk['name'] + '.meta')

        with open(split_metafile, "w") as f:
            yaml.safe_dump(split_metadata, f, default_flow_style=False)

    write_metafile(rules, splits, stratum)


def write_metafile(rules, splits, component):
    metadata = {'cache': component.get('cache'),
                'products': [{'artifact': a,
                              'components': sorted(set(splits[a]))}
                             for a, r in rules]}

    if component.get('kind', 'chunk') == 'chunk':
        unique_artifacts = sorted(set([a for a, r in rules]))
        metadata = {'cache': component.get('cache'),
                    'repo': component.get('repo'),
                    'ref': component.get('ref'),
                    'products': [{'artifact': a, 'files': sorted(splits[a])}
                                 for a in unique_artifacts]}

    metafile = os.path.join(component['baserockdir'],
                            component['name'] + '.meta')

    with open(metafile, "w") as f:
        yaml.safe_dump(metadata, f, default_flow_style=False)
