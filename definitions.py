#!/usr/bin/env python3
#
# Copyright (C) 2014  Codethink Limited
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

    def __init__(self):
        ''' Load all definitions from `cwd` tree. '''
        if self.__definitions != []:
            return

        for dirname, dirnames, filenames in os.walk("."):
            for filename in filenames:
                if not filename.endswith('.def'):
                    continue

                this = self._load(dirname, filename)
                name = self.lookup(this, 'name')
                if name != []:
                    self._insert(this)

                    for dependency in self.lookup(this, 'build-depends'):
                        if self.lookup(dependency, 'repo') != []:
                            self._insert(dependency)

                    for content in self.lookup(this, 'contents'):
                        if self.lookup(content, 'repo') != []:
                            self._insert(content)

            if '.git' in dirnames:
                dirnames.remove('.git')


    def _load(self, path, name):
        ''' Load a single definition file, and create a hash for it. '''
        try:
            filename = os.path.join(path, name)
            with open(filename) as f:
                text = f.read()

            definition = yaml.safe_load(text)
            if self.lookup(definition, 'repo'):
                definition['tree'] = cache.get_tree(definition)

        except ValueError:
            app.log(this, 'ERROR: problem loading', filename)

        return definition

    def _insert(self, this):
        for i, definition in enumerate(self.__definitions):
            if definition['name'] == this['name']:
                for key in this:
                    definition[key] = this[key]

                return

        self.__definitions.append(this)

    def get(self, this):
        ''' Load in the actual definition for a given named component.

        We may need to loop through the whole list to find the right entry.

        '''
        if (self.lookup(this, 'contents') != []
                or self.lookup(this, 'repo') != []):
            return this

        for definition in self.__definitions:
            if (definition['name'] == this
                or definition['name'].split('|')[0] == this
                or definition['name'] == self.lookup(this, 'name')
                or definition['name'].split('|')[0]
                    == self.lookup(this, 'name')):
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
            return this['name'].split('|')[1]
        except:
            return False
