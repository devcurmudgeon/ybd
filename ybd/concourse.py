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

import yaml
import ybd.app
from ybd.utils import log, timer

# Concourse data model:
# a 'resource' is an input line into a box
# a 'job' is a box on the diagram
# a 'job' has a 'plan' - a set of 'tasks' which operate on 'resources'


class Pipeline(object):

    def __init__(self, dn):

        self.resources = [{'name': dn['name'], 'type': 'foo'}]
        self.jobs = []
        self.config = {'run': {'path': 'ybd', 'args': []},
                       'platform': 'linux',
                       'image': 'docker:///devcurmudgeon/foo'}

        self.write_pipeline(dn)
        output = config.defs.get(dn)['name'] + '.yml'
        with open(output, 'w') as f:
            pipeline = {'resources': self.resources, 'jobs': self.jobs}
            f.write(yaml.dump(pipeline, default_flow_style=False))
        log('CONCOURSE', 'pipeline is at', output)

    def write_pipeline(self, dn):
        dn = config.defs.get(dn)
        self.add_resource(dn)
        aggregate = []
        for it in dn.get('build-depends', []) + dn.get('contents', []):
            component = config.defs.get(it)
            self.add_resource(component)
            if component.get('kind', 'chunk') == 'chunk':
                aggregate += [{'get': component['name']}]
            else:
                self.write_pipeline(component)
                aggregate += [{'get': component['name'],
                               'passed': [component['name']]}]

        self.add_job(dn, [{'aggregate': aggregate}, {'put': dn['name']}])

    def add_job(self, component, plan):
        found = False
        for job in self.jobs:
            if job['name'] == component['name']:
                found = True
                for i in plan:
                    if i not in job['plan']:
                        job['plan'] += i
        if not found:
            self.jobs += [{'name': component['name'], 'plan': plan}]

    def add_resource(self, component):
        found = False
        for resource in self.resources:
            if resource['name'] == component['name']:
                found = True
        if not found:
            if component.get('kind', 'chunk') == 'chunk':
                self.resources += [{'name': component['name'],
                                    'type': 'git',
                                    'source': {'uri': component.get('repo'),
                                               'branch': 'master'}}]
            else:
                self.resources += [{'name': component['name'], 'type': 'foo'}]
