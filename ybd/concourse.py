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
import os
import app
import repos


def write_pipeline(defs, target):
    target = defs.get(target)
    build = {}
    build['path'] = 'ybd'
    build['args'] = []
    config = {}
    config['run'] = build
    config['platform'] = 'linux'
    config['image'] = "docker:///devcurmudgeon/foo"

    pipeline = {}
    pipeline['resources'] = inputs(defs, target)

    aggregate = []
    for it in target.get('contents', []) + target.get('build-depends', []):
        component = defs.get(it)
        aggregate += [dict(get=component['name'])]

    plan = [dict(task='build', config=config), dict(aggregate=aggregate)]
    job = dict(name=os.path.basename(app.config['target']), plan=plan)
    pipeline['jobs'] = [job]

    output = './pipeline.yml'
    with open(output, 'w') as f:
        f.write(yaml.dump(pipeline,
                default_flow_style=False))

    app.exit('CONCOURSE', 'pipeline is at', output)


def inputs(defs, target):
    resources = []
    target = defs.get(target)
    for it in target.get('contents', []) + target.get('build-depends', []):
        resource = {}
        component = defs.get(it)
        resource['name'] = component['name']
        if component.get('repo'):
            resource['type'] = 'git'
            uri = repos.get_repo_url(component['repo'])
            source = dict(uri=uri, branch=component['ref'])
            source = dict(uri=uri, branch='master')
            resource['source'] = source
        resources += [resource]
    return resources


def plan(defs, target):
    return


def job(defs, target):
    component = defs.get(target)
    return
