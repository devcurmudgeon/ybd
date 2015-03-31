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
    __definitions = {}
    __trees = {}

    def __init__(self):
        ''' Load all definitions from `cwd` tree. '''
        if self.__definitions != {}:
            return

        for dirname, dirnames, filenames in os.walk(os.getcwd()):
            if '.git' in dirnames:
                dirnames.remove('.git')

            for filename in filenames:
                if not filename.endswith(('.def', '.morph')):
                    continue

                definition = self._load(os.path.join(dirname, filename))

                if definition.get('name'):
                    self._tidy(definition)
        try:
            self.__trees = self._load(os.getcwd(), ".trees")
            for definition in self.__definitions:
                definition['tree'] = self.__trees.get(definition['name'])

        except:
            return


    def _load(self, filename):
        ''' Load a single definition file '''
        try:
            with open(filename) as f:
                text = f.read()

            definition = yaml.safe_load(text)

            # handle old morph syntax...
            if definition.get('chunks'):
                definition['contents'] = definition.pop('chunks')
            if definition.get('strata'):
                definition['contents'] = definition.pop('strata')
            for subcomponent in (definition.get('build-depends', []) +
                                 definition.get('contents', [])):
                if subcomponent.get('morph'):
                    name = os.path.basename(subcomponent.pop('morph'))
                    subcomponent['name'] = os.path.splitext(name)[0]

        except ValueError:
            app.log(this, 'ERROR: problem loading', filename)

        return definition

    def _tidy(self, this):
        for index, dependency in enumerate(this.get('build-depends', [])):
            if type(dependency) is dict:
                 this['build-depends'][index] = dependency['name']

        for index, component in enumerate(this.get('contents', [])):
            if type(component) is dict and component.get('repo'):
                self._insert(component)
                component['build-depends'] = (this.get('build-depends', []) +
                                              component.get('build-depends', []))
                this['contents'][index] = component['name']

        self._insert(this)

    def _insert(self, this):
        definition = self.__definitions.get(this['name'])
        if definition:
            if definition.get('ref') is None or this.get('ref') is None:
                for key in this:
                    definition[key] = this[key]

            for key in this:
                if key == 'morph' or this[key] is None:
                    continue

                if definition.get(key) != this[key]:
                    app.log(this, 'WARNING: multiple definitions of', key)
                    app.log(this, '%s | %s' % (definition.get(key), this[key]))
        else:
            self.__definitions[this['name']] = this
            definition = self.__definitions.get(this['name'])

        return definition

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
            if self.__definitions.get(name).get('tree') is not None:
                self.__trees[name] = self.__definitions.get(name).get('tree')
        with open(os.path.join(os.getcwd(), '.trees'), 'w') as f:
            f.write(yaml.dump(self.__trees, default_flow_style=False))
