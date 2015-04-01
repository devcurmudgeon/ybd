#!/usr/bin/env python3
#
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

import yaml
import os
import app
import cache
from subprocess import check_output


class Definitions():
    __files = {}
    __definitions = {}
    __trees = {}

    def __init__(self, target=''):
        ''' Load all definitions from `cwd` tree. '''
        if self.__definitions != {}:
            return
        for dirname, dirnames, filenames in os.walk('.'):
            if '.git' in dirnames:
                dirnames.remove('.git')

            for filename in filenames:
                if filename.endswith(('.def', '.morph')):
                    this = self._load(dirname, filename)
                    path = os.path.join(dirname[2:], filename)
                    self.__files[path] = this
                    if path == target or this['name'] == target:
                        target = path
                        app.log(this, 'Target is', path)

        if not self.__files.get(target):
            app.log(target, 'ERROR: No definition found for', target)
            raise SystemExit

        self.define(target)

        try:
            self.__trees = self._load(".trees")
            for name in self.__definitions:
                self.__definitions[name]['tree'] = self.__trees.get(name)
        except:
            return

    def define(self, target):
        definition = self.__definitions.get(self.__files[target]['name'])
        if definition:
            return definition['name']
        this = self.__files[target]
        # handle old morph syntax...
        for subset in ['chunks', 'strata']:
            if this.get(subset):
                this['contents'] = this.pop(subset)
        for subset in ['build-depends', 'contents']:
            for component in this.get(subset, []):
                if type(component) is dict and component.get('morph'):
                    component['path'] = component.pop('morph')
                    self.define(component['path'])

        for index, dependency in enumerate(this.get('build-depends', [])):
            this['build-depends'][index] = self.define(dependency['path'])

        for index, component in enumerate(this.get('contents', [])):
            component['build-depends'] = (this.get('build-depends', []) +
                                          component.get('build-depends', []))
            this['contents'][index] = self._insert(component)

        return self._insert(this)

    def _load(self, dirname, filename):
        ''' Load a single definition file '''
        try:
            with open(os.path.join(dirname, filename)) as f:
                text = f.read()

            definition = yaml.safe_load(text)

        except ValueError:
            app.log(this, 'ERROR: problem loading', filename)

        return definition

    def _insert(self, this):
        definition = self.__definitions.get(this['name'])
        if definition:
            if definition.get('ref') is None or this.get('ref') is None:
                for key in this:
                    definition[key] = this[key]

            for key in this:
                if definition.get(key) != this[key]:
                    app.log(this, 'WARNING: multiple definitions of', key)
                    app.log(this, '%s | %s' % (definition.get(key), this[key]))
        else:
            self.__definitions[this['name']] = this

        return this['name']

    def get(self, this):
        if type(this) is str:
            return self.__definitions.get(this)
        return self.__definitions.get(this['name'])

    def version(self, this):
        try:
            return this['name'].split('@')[1]
        except:
            return False

    def save_trees(self):
        self.__trees = {}
        for name in self.__definitions:
            if self.__definitions[name].get('tree') is not None:
                self.__trees[name] = self.__definitions[name]['tree']
        with open(os.path.join(os.getcwd(), '.trees'), 'w') as f:
            f.write(yaml.dump(self.__trees, default_flow_style=False))
