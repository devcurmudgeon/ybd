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

import os
import random
from subprocess import call, check_output

import json
import app
import buildsystem
import cache
import repos
import sandbox
from shutil import copyfile
import utils


def deploy(defs, target):
    '''Deploy a cluster definition.'''

    deployment = target if type(target) is dict else defs.get(target)

    with app.timer(deployment, 'Starting deployment'):
        for system in deployment.get('systems', []):
            deploy_system(defs, system)


def deploy_system(defs, system_spec, parent_location=''):
    '''Deploy a system and subsystems recursively.

    Takes a system spec (i.e. an entry in the "systems" list in a cluster
    definition), and optionally a path to a parent system tree. If
    `parent_location` is given then the `location` given in the cluster
    definition for the subsystem is appended to `parent_location`, with
    the result being used as the location for the deployment extensions.

    '''
    system = defs.get(system_spec['path'])
    deploy_defaults = system_spec.get('deploy-defaults')

    if system.get('arch') and system['arch'] != app.settings['arch']:
        app.log(system, 'Skipping deployment for', system['arch'])
        return None

    sandbox.setup(system)
    app.log(system, 'Extracting system artifact into', system['sandbox'])
    with open(cache.get_cache(defs, system), 'r') as artifact:
        call(['tar', 'x', '--directory', system['sandbox']], stdin=artifact)

    for subsystem in system_spec.get('subsystems', []):
        if deploy_defaults:
            subsystem = dict(deploy_defaults.items() + subsystem.items())
        deploy_system(defs, subsystem, parent_location=system['sandbox'])

    for name, deployment in system_spec.get('deploy', {}).iteritems():
        method = os.path.basename(deployment['type'])
        if deploy_defaults:
            deployment = dict(deploy_defaults.items() + deployment.items())
        do_deployment_manifest(system, deployment)
        if parent_location:
            deployment['location'] = os.path.join(
                parent_location, deployment['location'].lstrip('/'))
        try:
            sandbox.run_extension(system, deployment, 'check', method)
        except KeyError:
            app.log(system, "Couldn't find a check extension for", method)

        for ext in system.get('configuration-extensions', []):
            sandbox.run_extension(system, deployment, 'configure',
                                  os.path.basename(ext))
        os.chmod(system['sandbox'], 0o755)
        sandbox.run_extension(system, deployment, 'write', method)
    sandbox.remove(system)


def assemble(defs, target):
    '''Assemble dependencies and contents recursively until target exists.'''

    if cache.get_cache(defs, target):
        return cache.cache_key(defs, target)

    component = defs.get(target)

    if component.get('arch') and component['arch'] != app.settings['arch']:
        app.log(target, 'Skipping assembly for', component.get('arch'))
        return None

    def assemble_system_recursively(system):
        assemble(defs, system['path'])
        for subsystem in system.get('subsystems', []):
            assemble_system_recursively(subsystem)

    with app.timer(component, 'Starting assembly'):
        sandbox.setup(component)
        for system_spec in component.get('systems', []):
            assemble_system_recursively(system_spec)

        dependencies = component.get('build-depends', [])
        random.shuffle(dependencies)
        for it in dependencies:
            dependency = defs.get(it)
            assemble(defs, dependency)
            sandbox.install(defs, component, dependency)

        contents = component.get('contents', [])
        random.shuffle(contents)
        for it in contents:
            subcomponent = defs.get(it)
            if subcomponent.get('build-mode') != 'bootstrap':
                assemble(defs, subcomponent)
                sandbox.install(defs, component, subcomponent)

        if 'systems' not in component:
            build(defs, component)
        do_manifest(component)
        cache.cache(defs, component,
                    full_root=component.get('kind') == "system")
        sandbox.remove(component)

    return cache.cache_key(defs, component)


def build(defs, this):
    '''Actually create an artifact and add it to the cache

    This is what actually runs ./configure, make, make install (for example)
    By the time we get here, all dependencies for 'this' have been assembled.
    '''

    app.log(this, 'Start build')

    if this.get('build-mode') != 'bootstrap':
        sandbox.ldconfig(this)

    if this.get('repo'):
        repos.checkout(this['name'], this['repo'], this['ref'], this['build'])

    get_build_commands(defs, this)
    env_vars = sandbox.env_vars_for_build(defs, this)

    app.log(this, 'Logging build commands to %s' % this['log'])
    for build_step in buildsystem.build_steps:
        if this.get(build_step):
            app.log(this, 'Running', build_step)
        for command in this.get(build_step, []):
            if command is False:
                command = "false"
            elif command is True:
                command = "true"
            sandbox.run_sandboxed(
                this, command, env=env_vars,
                allow_parallel=('build' in build_step))

    if this.get('devices'):
        sandbox.create_devices(this)

    with open(this['log'], "a") as logfile:
        logfile.write('Elapsed_time: %s\n' % app.elapsed(this['start-time']))


def get_build_commands(defs, this):
    '''Get commands specified in this, plus commmands implied by build_system

    If definition file doesn't exist, detect bs and use its commands.
    If bs is unspecified assume it's the manual build system.
    Use commands from the build system to fill in empty steps.
    '''

    if this.get('kind', None) == "system":
        # Systems must run their integration scripts as install commands
        this['install-commands'] = gather_integration_commands(defs, this)
        return

    if os.path.exists(this['path']):
        build_system = buildsystem.ManualBuildSystem()
        for bs in buildsystem.build_systems:
            if this.get('build-system') == bs.name:
                build_system = bs
    else:
        files = os.listdir(this['build'])
        build_system = buildsystem.detect_build_system(files)

    for build_step in buildsystem.build_steps:
        if this.get(build_step, None) is None:
            if build_step in build_system.commands:
                this[build_step] = build_system.commands[build_step]


def gather_integration_commands(defs, this):
    # 1. iterate all subcomponents (recursively) looking for sys-int commands
    # 2. gather them all up
    # 3. asciibetically sort them
    # 4. concat the lists

    def _gather_recursively(component, commands):
        if 'system-integration' in component:
            for product, it in component['system-integration'].iteritems():
                for name, cmdseq in it.iteritems():
                    commands["%s-%s" % (name, product)] = cmdseq
        for subcomponent in component.get('contents', []):
            _gather_recursively(defs.get(subcomponent), commands)

    all_commands = {}
    _gather_recursively(this, all_commands)
    result = []
    for key in sorted(all_commands.keys()):
        result.extend(all_commands[key])
    return result


def do_deployment_manifest(system, configuration):
    app.log(system, "Creating deployment manifest in", system['sandbox'])
    data = {'configuration': configuration}
    metafile = os.path.join(system['sandbox'], 'baserock', 'deployment.meta')
    with app.chdir(system['sandbox']), open(metafile, "w") as f:
        json.dump(data, f, indent=4, sort_keys=True, encoding='unicode-escape')
        f.flush()


def do_manifest(this):
    metafile = os.path.join(this['baserockdir'], this['name'] + '.meta')
    with app.chdir(this['install']), open(metafile, "w") as f:
        f.write("repo: %s\nref: %s\n" % (this.get('repo'), this.get('ref')))
        f.flush()
        call(['find'], stdout=f, stderr=f)
    copyfile(metafile, os.path.join(app.settings['artifacts'],
                                    this['cache'] + '.meta'))
