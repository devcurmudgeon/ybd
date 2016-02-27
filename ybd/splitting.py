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
from cache import get_cache, get_metadata, get_metafile
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
        app.log(component, 'Installing artifacts: ' + str(artifacts)
                + ' components: ' + str(components))

    baserockpath = os.path.join(component['sandbox'], 'baserock')
    if not os.path.isdir(baserockpath):
        os.mkdir(baserockpath)
    split_stratum_metafile = os.path.join(baserockpath,
                                          stratum['name'] + '.meta')
    with open(split_stratum_metafile, "w") as f:
        yaml.safe_dump(split_stratum_metadata, f, default_flow_style=False)

    for path in stratum['contents']:
        chunk = defs.get(path)
        if chunk.get('build-mode', 'staging') == 'bootstrap':
            continue

        metafile = os.path.join(get_cache(defs, chunk) + '.unpacked',
                                'baserock', chunk['name'] + '.meta')
        try:
            with open(metafile, "r") as f:
                filelist = []
                metadata = yaml.safe_load(f)
                split_metadata = {'ref': metadata['ref'],
                                  'repo': metadata['repo'],
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
            app.log(stratum, 'WARNING: problem loading ', metafile)


def check_overlaps(defs, component):
    if set(app.config['new-overlaps']) <= set(app.config['overlaps']):
        app.config['new-overlaps'] = []
        return

    app.config['new-overlaps'] = list(set(app.config['new-overlaps']))
    for path in app.config['new-overlaps']:
        app.log(component, 'WARNING: overlapping path', path)
        for filename in os.listdir(component['baserockdir']):
            with open(os.path.join(component['baserockdir'], filename)) as f:
                for line in f:
                    if path[1:] in line:
                        app.log(filename, 'WARNING: overlap at', path[1:])
                        break

    app.config['overlaps'] = list(set(app.config['new-overlaps'] +
                                      app.config['overlaps']))
    app.config['new-overlaps'] = []


def write_metadata(defs, component):
    kind = component.get('kind', 'chunk')
    if kind == 'chunk':
        write_chunk_metafile(defs, component)
    elif kind == 'stratum':
        write_stratum_metafiles(defs, component)
    check_overlaps(defs, component)


def compile_rules(defs, component):
    split_rules = component.get('products', [])
    default_rules = defs.defaults.get_split_rules(component.get('kind',
                                                                'chunk'))
    match_rules = OrderedDict((r.get('artifact'), r.get('include'))
                              for r in (split_rules + default_rules))

    rules = OrderedDict((component['name'] + a if a.startswith('-') else a,
                          re.compile('^(?:%s)$' % '|'.join(r)))
                          for a, r in match_rules.iteritems())
    return rules


def write_chunk_metafile(defs, chunk):
    '''Writes a chunk .meta file to the baserock dir of the chunk

    The split rules are used to divide up the installed files for the chunk
    into artifacts in the 'products' list

    '''
    app.log(chunk['name'], 'splitting chunk')
    rules = compile_rules(defs, chunk)
    splits = {a: [] for a in rules.keys()}

    install_dir = chunk['install']
    fs = OSFS(install_dir)
    files = fs.walkfiles('.', search='depth')
    dirs = fs.walkdirs('.', search='depth')

    for path in files:
        for artifact, rule in rules.iteritems():
            if rule.match(path):
                splits[artifact].append(path)
                break

    all_files = [a for x in splits.values() for a in x]
    for path in dirs:
        if not any(map(lambda y: y.startswith(path),
                   all_files)) and path != '':
            for artifact, rule in rules.iteritems():
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

    app.log(stratum['name'], 'splitting stratum')
    rules = compile_rules(defs, stratum)
    splits = {a: [] for a in rules.keys()}

    for item in stratum['contents']:
        chunk = defs.get(item)
        if chunk.get('build-mode', 'staging') == 'bootstrap':
            continue

        metadata = get_metadata(defs, chunk)
        split_metadata = {'ref': metadata['ref'],
                          'repo': metadata['repo'],
                          'products': []}

        chunk_artifacts = defs.get(chunk).get('artifacts', {})
        for artifact, target in chunk_artifacts.items():
            splits[target].append(artifact)

        for element in metadata['products']:
            for artifact, rule in rules.iteritems():
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
    metadata = {'products': [{'artifact': a,
                              'components': sorted(set(splits[a]))}
                             for a, r in rules.iteritems()]}

    if component.get('kind', 'chunk') == 'chunk':
        unique_artifacts = sorted(set([a for a, r in rules.iteritems()]))
        metadata = {'repo': component.get('repo'),
                    'ref': component.get('ref'),
                    'products': [{'artifact': a, 'files': sorted(splits[a])}
                                 for a in unique_artifacts]}

    metafile = os.path.join(component['baserockdir'],
                            component['name'] + '.meta')

    with open(metafile, "w") as f:
        yaml.safe_dump(metadata, f, default_flow_style=False)
