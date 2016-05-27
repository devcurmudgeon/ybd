# Copyright (C) 2016  Codethink Limited
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

import sys
import yaml
import os
from app import config, exit, log, setup, timer
from definitions import Definitions
import cache
from repos import get_repo_url


def inputs(defs, target):
    target = defs.get(target)
    resources = []
    for it in target.get('contents', []) + target.get('build-depends', []):
        component = defs.get(it)
        if component.get('repo'):
            resource = {'name': component['name'],
                        'type': 'git',
                        'source': {'uri': get_repo_url(component['repo']),
                                   'branch': component['ref']}}
        else:
            resource = {'name': component['name'], 'type': 'foo'}

        resources += [resource]
    return resources


def plan(defs, target):
    return


def job(defs, target):
    component = defs.get(target)
    return


def write_pipeline(defs, target):
    target = defs.get(target)
    config = {'run': {'path': 'ybd', 'args': []},
              'platform': 'linux',
              'image': 'docker:///devcurmudgeon/foo'}

    aggregate = []
    passed = []
    for it in target.get('contents', []) + target.get('build-depends', []):
        component = defs.get(it)
        if component.get('repo'):
            log('AGGREGATE', 'Adding aggregate for', component['name'])
            aggregate += [{'get': component['name']}]
        else:
            log('PASSED', 'Adding passed for', component['name'])
            aggregate += [{'get': component['name']}]
            passed += [component['name']]

    plan = [{'task': 'Build', 'config': config}, {'aggregate': aggregate}]
    job = {'name': target['name'], 'plan': plan, 'passed': passed}
    pipeline = {'resources': inputs(defs, target), 'jobs': [job]}

    output = './pipeline.yml'
    with open(output, 'w') as f:
        f.write(yaml.dump(pipeline, default_flow_style=False))

    exit('CONCOURSE', 'pipeline is at', output)


setup(sys.argv)

with timer('TOTAL'):
    target = os.path.join(config['defdir'], config['target'])
    log('TARGET', 'Target is %s' % target, config['arch'])
    with timer('DEFINITIONS', 'parsing %s' % config['def-version']):
        defs = Definitions()
    with timer('CACHE-KEYS', 'cache-key calculations'):
        cache.cache_key(defs, config['target'])
    write_pipeline(defs, config['target'])
