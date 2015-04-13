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

        for dirname, dirnames, filenames in os.walk('.'):
            if '.git' in dirnames:
                dirnames.remove('.git')
            for filename in filenames:
                if filename.endswith(('.def', '.morph')):
                    definition = self._load(os.path.join(dirname, filename))
        try:
            self.__trees = self._load(".trees")
            for name in self.__definitions:
                self.__definitions[name]['tree'] = self.__trees.get(name)
        except:
            return

    def _load(self, path):
        ''' Load a single definition file '''
        try:
            with open(path) as f:
                text = f.read()
            definition = yaml.safe_load(text)
        except ValueError:
            app.log(this, 'ERROR: problem loading', filename)
            return None

        definition['path'] = path[2:]
        self._fix_path_name(definition)

        # handle morph syntax oddities...
        for index, component in enumerate(definition.get('build-depends', [])):
            self._fix_path_name(component)
            definition['build-depends'][index] = self._insert(component)

        for subset in ['chunks', 'strata']:
            if definition.get(subset):
                definition['contents'] = definition.pop(subset)

        lookup = {}
        for index, component in enumerate(definition.get('contents', [])):
            self._fix_path_name(component)
            lookup[component['name']] = component['path']
            if component['name'] == definition['name']:
                app.log(definition, 'WARNING: %s contains' % definition['name'],
                        component['name'])
            for x, it in enumerate(component.get('build-depends', [])):
                component['build-depends'][x] = lookup.get(it, it)

            component['build-depends'] = (definition.get('build-depends', []) +
                                          component.get('build-depends', []))
            definition['contents'][index] = self._insert(component)

        return self._insert(definition)

    def _fix_path_name(self, this, name='ERROR'):
        if this.get('path', None) is None:
            this['path'] = this.pop('morph', this.get('name', name))
            if this['path'] == 'ERROR':
                app.log(this, 'ERROR: no path, no name?')
                raise SystemExit
        if this.get('name') is None:
            this['name'] = this['path'].replace('/', '-')
        if this['name'] == app.settings['target']:
            app.settings['target'] = this['path']

    def _insert(self, this):
        definition = self.__definitions.get(this['path'])
        if definition:
            if definition.get('ref') is None or this.get('ref') is None:
                for key in this:
                    definition[key] = this[key]

            for key in this:
                if definition.get(key) != this[key]:
                    app.log(this, 'WARNING: multiple definitions of', key)
                    app.log(this, '%s | %s' % (definition.get(key), this[key]))
        else:
            self.__definitions[this['path']] = this

        return this['path']

    def get(self, this):
        if type(this) is str:
            return self.__definitions.get(this)

        return self.__definitions.get(this['path'])

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
