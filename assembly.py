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

import app
import buildsystem
import cache
import repos
import sandbox
import shutil
import utils
from definitions import Definitions


def deploy(target):
    '''Deploy a cluster definition.'''

    defs = Definitions()
    deployment = target if type(target) is dict else defs.get(target)

    with app.timer(deployment, 'Starting deployment'):
        for system in deployment.get('systems', []):
            deploy_system(system)


def deploy_system(system_spec, parent_location=''):
    '''Deploy a system and subsystems recursively.

    Takes a system spec (i.e. an entry in the "systems" list in a cluster
    definition), and optionally a path to a parent system tree. If
    `parent_location` is given then the `location` given in the cluster
    definition for the subsystem is appended to `parent_location`, with
    the result being used as the location for the deployment extensions.

    '''
    defs = Definitions()
    system = defs.get(system_spec['path'])

    if system.get('arch') and system['arch'] != app.settings['arch']:
        app.log(system, 'Skipping deployment for', system['arch'])
        return None

    sandbox.setup(system)
    app.log(system, 'Extracting system artifact into', system['sandbox'])
    with open(cache.get_cache(system), 'r') as artifact:
        call(['tar', 'x', '--directory', system['sandbox']],
              stdin=artifact)

    for subsystem_spec in system_spec.get('subsystems', []):
        deploy_system(subsystem_spec, parent_location=system['sandbox'])

    for name, deployment in system_spec.get('deploy', {}).iteritems():
        method = os.path.basename(deployment['type'])
        if parent_location:
            deployment['location'] = os.path.join(
                parent_location, deployment['location'].lstrip('/'))
        try:
            sandbox.run_extension(system, deployment, 'check', method)
        except KeyError:
            app.log(system, "Couldn't find a check extension for",
                    method)
        for ext in system.get('configuration-extensions', []):
            sandbox.run_extension(system, deployment, 'configure',
                                  os.path.basename(ext))
        os.chmod(system['sandbox'], 0o755)
        sandbox.run_extension(system, deployment, 'write', method)
    sandbox.remove(system)


def assemble(target):
    '''Assemble dependencies and contents recursively until target exists.'''

    if cache.get_cache(target):
        return cache.cache_key(target)

    defs = Definitions()
    this = defs.get(target)

    if this.get('arch') and this['arch'] != app.settings['arch']:
        app.log(target, 'Skipping assembly for', this['arch'])
        return None

    with app.timer(this, 'Starting assembly'):
        sandbox.setup(this)
        for it in this.get('systems', []):
            system = defs.get(it)
            assemble(system)
            for subsystem in this.get('subsystems', []):
                assemble(subsystem)

        dependencies = this.get('build-depends', [])
        random.shuffle(dependencies)
        for it in dependencies:
            dependency = defs.get(it)
            assemble(dependency)
            sandbox.install(this, dependency)

        contents = this.get('contents', [])
        random.shuffle(contents)
        for it in contents:
            component = defs.get(it)
            if component.get('build-mode') != 'bootstrap':
                assemble(component)
                sandbox.install(this, component)

        build(this)
        do_manifest(this)
        cache.cache(this, full_root=this.get('kind', None) == "system")
        sandbox.remove(this)

    return cache.cache_key(this)


def build(this):
    '''Actually create an artifact and add it to the cache

    This is what actually runs ./configure, make, make install (for example)
    By the time we get here, all dependencies for 'this' have been assembled.
    '''

    app.log(this, 'Start build')

    if this.get('build-mode') != 'bootstrap':
        sandbox.ldconfig(this)

    if this.get('repo'):
        repos.checkout(this['name'], this['repo'], this['ref'], this['build'])

    get_build_commands(this)
    env_vars = sandbox.env_vars_for_build(this)

    app.log(this, 'Logging build commands to %s' % this['log'])
    for build_step in buildsystem.build_steps:
        if this.get(build_step):
            app.log(this, 'Running', build_step)
        for command in this.get(build_step, []):
            sandbox.run_sandboxed(
                this, command, env=env_vars,
                allow_parallel=('build' in build_step))

    if this.get('devices'):
        sandbox.create_devices(this)


def get_build_commands(this):
    '''Get commands specified in this, plus commmands implied by build_system

    If definition file doesn't exist, detect bs and use its commands.
    If bs is unspecified assume it's the manual build system.
    Use commands from the build system to fill in empty steps.
    '''

    if this.get('kind', None) == "system":
        # Systems must run their integration scripts as install commands
        this['install-commands'] = gather_integration_commands(this)
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


def gather_integration_commands(this):
    # 1. iterate all subcomponents (recursively) looking for sys-int commands
    # 2. gather them all up
    # 3. asciibetically sort them
    # 4. concat the lists

    defs = Definitions()

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


def do_manifest(this):
    metafile = os.path.join(this['baserockdir'], this['name'] + '.meta')
    with app.chdir(this['install']), open(metafile, "w") as f:
        f.write("repo: %s\nref: %s\n" % (this.get('repo'), this.get('ref')))
        f.write('elapsed_time: %s\n' % app.elapsed(this['start-time']))
        f.flush()
        call(['find'], stdout=f, stderr=f)
