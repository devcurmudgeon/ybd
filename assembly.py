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
import cache
import repos
import sandbox
from shutil import copyfile
import utils
import datetime
import splitting
import yaml


def deploy(defs, target):
    '''Deploy a cluster definition.'''

    deployment = target if type(target) is dict else defs.get(target)

    with app.timer(deployment, 'deployment'):
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

    if system.get('arch') and system['arch'] != app.config['arch']:
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
        # needed for artifact splitting
        load_manifest(defs, target)
        return cache.cache_key(defs, target)

    random.seed(datetime.datetime.now())
    component = defs.get(target)

    if component.get('arch') and component['arch'] != app.config['arch']:
        app.log(target, 'Skipping assembly for', component.get('arch'))
        return None

    def assemble_system_recursively(system):
        assemble(defs, system['path'])

        for subsystem in system.get('subsystems', []):
            assemble_system_recursively(subsystem)

    with app.timer(component, 'assembly'):
        sandbox.setup(component)

        systems = component.get('systems', [])
        random.shuffle(systems)
        for system in systems:
            assemble_system_recursively(system)

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
                splits = None
                if component.get('kind') == 'system':
                    splits = subcomponent.get('artifacts')
                sandbox.install(defs, component, subcomponent, splits)

        app.config['counter'] += 1
        if 'systems' not in component:
            with app.timer(component, 'build'):
                build(defs, component)
        with app.timer(component, 'artifact creation'):
            do_manifest(defs, component)
            cache.cache(defs, component,
                        full_root=component.get('kind') == "system")
        sandbox.remove(component)

    return cache.cache_key(defs, component)


def build(defs, this):
    '''Actually create an artifact and add it to the cache

    This is what actually runs ./configure, make, make install (for example)
    By the time we get here, all dependencies for 'this' have been assembled.
    '''

    if this.get('build-mode') != 'bootstrap':
        sandbox.ldconfig(this)

    if this.get('repo'):
        repos.checkout(this['name'], this['repo'], this['ref'], this['build'])

    get_build_commands(defs, this)
    env_vars = sandbox.env_vars_for_build(defs, this)

    app.log(this, 'Logging build commands to %s' % this['log'])
    for build_step in defs.defaults.build_steps:
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
    '''Get commands specified in 'this', plus commands implied by build-system

    The containing definition may point to another definition file (using
    the 'path' field in YBD's internal data model) that contains build
    instructions, or it may only specify a predefined build system, using
    'build-system' field.

    The definition containing build instructions can specify a predefined
    build-system and then override some or all of the command sequences it
    defines.

    If the definition file doesn't exist and no build-system is specified,
    this function will scan the contents the checked-out source repo and try
    to autodetect what build system is used.

    '''

    if this.get('kind') == "system":
        # Systems must run their integration scripts as install commands
        this['install-commands'] = gather_integration_commands(defs, this)
        return

    if this.get('build-system') or os.path.exists(this['path']):
        build_system = this.get('build-system', 'manual')
        app.log(this, 'Defined build system is', build_system)
    else:
        files = os.listdir(this['build'])
        build_system = defs.defaults.detect_build_system(files)
        app.log(this, 'Autodetected build system is', build_system)

    for build_step in defs.defaults.build_steps:
        if this.get(build_step) is None:
            this[build_step] = \
                defs.defaults.build_systems[build_system].get(build_step, [])


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


def do_manifest(defs, this):
    metafile = os.path.join(this['baserockdir'], this['name'] + '.meta')
    metadata = {}
    metadata['repo'] = this.get('repo')
    metadata['ref'] = this.get('ref')
    kind = this.get('kind', 'chunk')

    if kind == 'chunk':
        metadata['products'] = splitting.do_chunk_splits(defs, this, metafile)
    elif kind == 'stratum':
        metadata['products'] = splitting.do_stratum_splits(defs, this)

    if metadata.get('products'):
        defs.set_member(this['path'], '_artifacts', metadata['products'])

    with app.chdir(this['install']), open(metafile, "w") as f:
        yaml.safe_dump(metadata, f, default_flow_style=False)

    copyfile(metafile, os.path.join(app.config['artifacts'],
                                    this['cache'] + '.meta'))


def load_manifest(defs, target):
    cachepath, cachedir = os.path.split(cache.get_cache(defs, target))
    metafile = cachepath + ".meta"
    metadata = None
    definition = defs.get(target)
    name = definition['name']

    path = None
    if type(target) is str:
        path = target
    else:
        path = target['name']

    try:
        with open(metafile, "r") as f:
            metadata = yaml.safe_load(f)
    except:
        app.log(name, 'WARNING: problem loading metadata', metafile)
        return None

    if metadata:
        app.log(name, 'loaded metadata for', path)
        defs.set_member(path, '_loaded', True)
        if metadata.get('products'):
            defs.set_member(path, '_artifacts', metadata['products'])
