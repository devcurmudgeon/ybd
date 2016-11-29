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

import os
from subprocess import call
import json
from ybd import app, cache, sandbox
from ybd.utils import log


def deploy(target):
    '''Deploy a cluster definition.'''
    arch = config.config['arch']
    for system in target.get('systems', []):
        if app.defs.get(system).get('arch', arch) == arch:
            with app.timer(system, 'deployment'):
                deploy_system(system)


def deploy_system(system_spec, parent_location=''):
    '''Deploy a system and subsystems recursively.

    Takes a system spec (i.e. an entry in the "systems" list in a cluster
    definition), and optionally a path to a parent system tree. If
    `parent_location` is given then the `location` given in the cluster
    definition for the subsystem is appended to `parent_location`, with
    the result being used as the location for the deployment extensions.

    '''
    system = app.defs.get(system_spec['path'])
    if not cache.get_cache(system):
        log('DEPLOY', 'System is not built, cannot deploy:\n', system,
                exit=True)
    deploy_defaults = system_spec.get('deploy-defaults')

    with sandbox.setup(system):
        log(system, 'Extracting system artifact into', system['sandbox'])
        with open(cache.get_cache(system), 'r') as artifact:
            call(['tar', 'x', '--directory', system['sandbox']],
                 stdin=artifact)

        for subsystem in system_spec.get('subsystems', []):
            if deploy_defaults:
                subsystem = dict(deploy_defaults.items() + subsystem.items())
            deploy_system(subsystem, parent_location=system['sandbox'])

        for name, deployment in system_spec.get('deploy', {}).items():
            method = deployment.get('type') or deployment.get('upgrade-type')
            method = os.path.basename(method)
            if deploy_defaults:
                deployment = dict(deploy_defaults.items() + deployment.items())
            do_deployment_manifest(system, deployment)
            if parent_location:
                for l in ['location', 'upgrade-location']:
                    if l in deployment:
                        dn = deployment[l].lstrip('/')
                        deployment[l] = os.path.join(parent_location, dn)
            try:
                sandbox.run_extension(system, deployment, 'check', method)
            except KeyError:
                log(system, "Couldn't find a check extension for", method)

            for ext in system.get('configuration-extensions', []):
                sandbox.run_extension(system, deployment, 'configure',
                                      os.path.basename(ext))
            os.chmod(system['sandbox'], 0o755)
            sandbox.run_extension(system, deployment, 'write', method)


def do_deployment_manifest(system, configuration):
    log(system, "Creating deployment manifest in", system['sandbox'])
    data = {'configuration': configuration}
    metafile = os.path.join(system['sandbox'], 'baserock', 'deployment.meta')
    with app.chdir(system['sandbox']), open(metafile, "w") as f:
        json.dump(data, f, indent=4, sort_keys=True, encoding='unicode-escape')
        f.flush()
