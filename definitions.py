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
    __definitions = []
    __trees = {}

    def __init__(self):
        ''' Load all definitions from `cwd` tree. '''
        if self.__definitions != []:
            return

        for dirname, dirnames, filenames in os.walk(os.getcwd()):
            for filename in filenames:
                if not (filename.endswith('.def') or
                        filename.endswith('.morph')):
                    continue

                this = self._load(dirname, filename)
                name = self.lookup(this, 'name')
                if name != []:
                    self._insert(this)

                    for dependency in self.lookup(this, 'build-depends'):
                        if self.lookup(dependency, 'repo') != []:
                            self._insert(dependency)

                    for component in self.lookup(this, 'contents'):
                        component['build-depends'] = (
                            self.lookup(component, 'build-depends'))
                        for dependency in self.lookup(this, 'build-depends'):
                            component['build-depends'].insert(0,
                                self.lookup(dependency, 'name'))
                        self._insert(component)

            if '.git' in dirnames:
                dirnames.remove('.git')

        try:
            self.__trees = self._load(os.getcwd(), ".trees")
            for definition in self.__definitions:
                definition['tree'] = self.__trees.get(definition['name'])

        except:
            return

    def _load(self, path, name):
        ''' Load a single definition file '''
        try:
            filename = os.path.join(path, name)
            with open(filename) as f:
                text = f.read()

            definition = yaml.safe_load(text)

            # handle old morph syntax...
            if definition.get('chunks'):
                definition['contents'] = definition.pop('chunks')
            if definition.get('strata'):
                definition['contents'] = definition.pop('strata')
            for it in (self.lookup(definition, 'build-depends') +
                       self.lookup(definition, 'contents')):
                if it.get('morph'):
                    path = it.pop('morph')
                    it['name'] = os.path.splitext(os.path.basename(path))[0]

        except ValueError:
            app.log(this, 'ERROR: problem loading', filename)

        return definition

    def _insert(self, this):
        for i, definition in enumerate(self.__definitions):
            if definition['name'] == this['name']:
                if (self.lookup(definition, 'ref') == [] or
                        self.lookup(definition, 'ref') is None or
                        self.lookup(this, 'ref') == []):
                    for key in this:
                        definition[key] = self.lookup(this, key)

                    return

                for key in this:
                    if key == 'morph' or this[key] is None:
                        continue

                    if definition[key] != this[key]:
                        app.log(this, 'WARNING: multiple definitions of', key)
                        app.log(this, '%s | %s' % (definition[key], this[key]))

        self.__definitions.append(this)

    def get(self, this):
        for definition in self.__definitions:
            if (definition['name'] == this or
                    definition['name'] == self.lookup(this, 'name')):
                return definition

        app.log(this, 'ERROR: no definition found for', this)
        raise SystemExit

    def lookup(self, thing, value):
        ''' Look up value from thing, return [] if none. '''
        val = []
        try:
            val = thing[value]
        except:
            pass
        return val

    def version(self, this):
        try:
            return this['name'].split('@')[1]
        except:
            return False

    def save_trees(self):
        self.__trees = {}
        for definition in self.__definitions:
            if definition.get('tree') is not None:
                self.__trees[definition['name']] = definition.get('tree')
        with open(os.path.join(os.getcwd(), '.trees'), 'w') as f:
            f.write(yaml.dump(self.__trees, default_flow_style=False))
