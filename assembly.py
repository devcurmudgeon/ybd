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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# =*= License: GPL-2 =*=

import os
from definitions import Definitions
import cache
import repos
import app
import buildsystem
import sandbox
import shutil
import tempfile
import utils
from subprocess import check_output
from subprocess import call

def assemble(target):
    '''Assemble whatever we're given, until the target is fulfilled'''
    defs = Definitions()
    this = defs.get(target)

    if this.get('kind') == 'cluster':
        return assemble_as_deploy(target)
    else:
        return assemble_as_build(target)

def assemble_as_deploy(target):
    defs = Definitions()
    this = defs.get(target)
    extensions = utils.find_extensions()
    for system in this.get('systems', []):
        # 1. assemble the system
        key = assemble(system.get('morph', 'MISSING KEY: morph in system %r' % system))
        # 2. do something with it
        for name, deployment in system.get('deploy',{}).iteritems():
            deployment['name'] = "%s.%s.%s" % (this['name'], key, name)
            with app.timer(deployment, 'Deployment begins'):
                tempfile.tempdir = app.settings['deployment']
                deploy_base = tempfile.mkdtemp()
                app.log(deployment, "Staging deployment in %s" % deploy_base)
                try:
                    write_method = deployment['type']
                    # 2.1 Run the check extension for the write method
                    if write_method in extensions['check']:
                        utils.run_deployment_extension(
                            deployment,
                            [extensions['check'][write_method],
                             deployment['location']],
                            'Running write method pre-check')
                    # 2.2 Extract the system
                    app.log(deployment, "Extracting system artifact")
                    artifact_filename = os.path.join(app.settings['artifacts'],
                                                     key + '.tar.gz')
                    with open(artifact_filename, "r") as artifile:
                        call(['tar', 'x', '--directory',
                              deploy_base], stdin=artifile)
                    # 2.3 Run configuration extensions from the system
                    system_def = defs.get(system['morph'])
                    for conf_ext in system_def.get('configuration-extensions', []):
                        utils.run_deployment_extension(
                            deployment,
                            [extensions['configure'][conf_ext], deploy_base],
                            'Running configuration extension')
                    # 2.4 Fix up permissions on the "/" of the target
                    os.chmod(deploy_base, 0o755)
                    # 2.5 Run the write method
                    utils.run_deployment_extension(
                        deployment,
                        [extensions['write'][write_method], deploy_base,
                         deployment['location']],
                        'Running write method')
                finally:
                    app.log(deployment, "Cleaning up")
                    shutil.rmtree(deploy_base)
    return cache.cache_key(target)

def assemble_as_build(target):
    '''Assemble dependencies and contents recursively until target exists.'''

    if cache.get_cache(target):
        return cache.cache_key(target)

    defs = Definitions()
    this = defs.get(target)

    with app.timer(this, 'Starting assembly'):
        with sandbox.setup(this):
            for it in this.get('build-depends', []):
                dependency = defs.get(it)
                assemble(dependency)
                sandbox.install(this, dependency,
                                force_copy=this.get('kind', None) == "system")

            for it in this.get('contents', []):
                component = defs.get(it)
                if component.get('build-mode') != 'bootstrap':
                    assemble(component)
                    sandbox.install(this, component,
                                    force_copy=this.get('kind',
                                                        None) == "system")

            if this.get('build-mode') != 'bootstrap':
                sandbox.ldconfig(this)
            else:
                app.log(this, "No ldconfig because bootstrap mode is engaged")

            build(this)
            if this.get('devices'):
                sandbox.create_devices(this)
            do_manifest(this)
            app.log(this, "Constructing artifact")
            cache.cache(this, full_root=this.get('kind', None) == "system")
            sandbox.remove(this)
    return cache.cache_key(this)

def build(this):
    '''Actually create an artifact and add it to the cache

    This is what actually runs ./configure, make, make install (for example)
    By the time we get here, all dependencies for 'this' have been assembled.
    '''

    app.log(this, 'Start build')
    defs = Definitions()
    if this.get('repo'):
        repos.checkout(this['name'], this['repo'], this['ref'], this['build'])

    get_build_commands(this)
    for build_step in buildsystem.build_steps:
        if this.get(build_step):
            app.log(this, 'Running', build_step)
        for command in this.get(build_step, []):
            sandbox.run_sandboxed(this, command,
                                  allow_parallel=('build' in build_step),
                                  readwrite_root=(this.get('kind') == 'system'))


def get_build_commands(this):
    '''Get commands specified in this, plus commmands implied by build_system

    If bs is unspecified and all steps are empty, detect bs & use its commands
    If bs is specified, use its commands for empty steps

    This logic is rather convoluted, because there are examples of morph files
    where build-system is unspecified. It boils down to:
        if bs is specified, or all steps are empty, fill any empty steps
    '''

    build_system = None
    for bs in buildsystem.build_systems:
        if this.get('build-system') == bs.name:
            build_system = bs

    if not build_system:
        for build_step in buildsystem.build_steps:
            if this.get(build_step):
                return

        files = check_output(['ls', this['build']]).decode("utf-8").splitlines()
        build_system = buildsystem.detect_build_system(files)

    for build_step in buildsystem.build_steps:
        if this.get(build_step, None) is None:
            if build_system.commands.get(build_step):
                this[build_step] = build_system.commands.get(build_step)

    if this.get('kind', None) == "system":
        # Systems must run their integration scripts as install commands
        this['install-commands'] = gather_integration_commands(this)

def gather_integration_commands(this):
    # 1. iterate all subcomponents (recursively) looking for sys-int commands
    # 2. gather them all up
    # 3. asciibetically sort them
    # 4. concat the lists

    defs = Definitions()

    def _gather_recursively(component, commands):
        if 'system-integration' in component:
            for product, integrations in component['system-integration'].iteritems():
                for name, cmdseq in integrations.iteritems():
                    commands["%s-%s" % (name, product)] = cmdseq
        for subcomp in component.get('contents', []):
            _gather_recursively(defs.get(subcomp), commands)

    all_commands = {}
    _gather_recursively(this, all_commands)
    result = []
    for key in sorted(all_commands.keys()):
        result.extend(all_commands[key])
    return None if result == [] else result

def do_manifest(this):
    metafile = os.path.join(this['baserockdir'], this['name'] + '.meta')
    with app.chdir(this['install']), open(metafile, "w") as f:
        call(['find'], stdout=f, stderr=f)
