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

import yaml
import os
import app
import cache
from subprocess import check_output, PIPE
import hashlib


class Definitions():
    __definitions = {}
    __trees = {}

    def __init__(self):
        ''' Load all definitions from `cwd` tree. '''
        if self.__definitions != {}:
            return

        json_schema = self._load(app.settings.get('json-schema'))
        definitions_schema = self._load(app.settings.get('defs-schema'))
        if json_schema and definitions_schema:
            import jsonschema as js
            js.validate(json_schema, json_schema)
            js.validate(definitions_schema, json_schema)

        things_have_changed = not self._check_trees()
        for dirname, dirnames, filenames in os.walk('.'):
            if '.git' in dirnames:
                dirnames.remove('.git')
            for filename in filenames:
                if filename.endswith(('.def', '.morph')):
                    contents = self._load(os.path.join(dirname, filename))
                    if contents is not None:
                        if things_have_changed and definitions_schema:
                            app.log(filename, 'Validating schema')
                            js.validate(contents, definitions_schema)
                        self._tidy(contents)

        if self._check_trees():
            for name in self.__definitions:
                self.__definitions[name]['tree'] = self.__trees.get(name)

    def _load(self, path):
        try:
            with open(path) as f:
                text = f.read()
            contents = yaml.safe_load(text)
        except:
            app.log('DEFINITIONS', 'WARNING: problem loading', path)
            return None
        contents['path'] = path[2:]
        return contents

    def _tidy(self, this):
        ''' Load a single definition file '''

        self._fix_path_name(this)

        # handle morph syntax oddities...
        for system in this.get('systems', []):
            self._fix_path_name(system)
            for subsystem in system.get('subsystems', []):
                self._fix_path_name(subsystem)

        for index, component in enumerate(this.get('build-depends', [])):
            self._fix_path_name(component)
            this['build-depends'][index] = self._insert(component)

        for subset in ['chunks', 'strata']:
            if this.get(subset):
                this['contents'] = this.pop(subset)

        lookup = {}
        for index, component in enumerate(this.get('contents', [])):
            self._fix_path_name(component)
            lookup[component['name']] = component['path']
            if component['name'] == this['name']:
                app.log(this, 'WARNING: %s contains' % this['name'],
                        component['name'])
            for x, it in enumerate(component.get('build-depends', [])):
                component['build-depends'][x] = lookup.get(it, it)

            component['build-depends'] = (this.get('build-depends', []) +
                                          component.get('build-depends', []))
            this['contents'][index] = self._insert(component)

        return self._insert(this)

    def _fix_path_name(self, this, name='ERROR'):
        if this.get('path', None) is None:
            this['path'] = this.pop('morph', this.get('name', name))
            if this['path'] == 'ERROR':
                app.exit(this, 'ERROR: no path, no name?')
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

    def _check_trees(self):
        try:
            with app.chdir(app.settings['defdir']):
                checksum = check_output('ls -lRA */', shell=True)
            checksum = hashlib.md5(checksum).hexdigest()
            with open('.trees') as f:
                text = f.read()
            self.__trees = yaml.safe_load(text)
            if self.__trees.get('.checksum') == checksum:
                return True
        except:
            if os.path.exists('.trees'):
                os.remove('.trees')
            self.__trees = {}
            return False

    def save_trees(self):
        with app.chdir(app.settings['defdir']):
            checksum = check_output('ls -lRA */', shell=True)
        checksum = hashlib.md5(checksum).hexdigest()
        self.__trees = {'.checksum': checksum}
        for name in self.__definitions:
            if self.__definitions[name].get('tree') is not None:
                self.__trees[name] = self.__definitions[name]['tree']

        with open(os.path.join(os.getcwd(), '.trees'), 'w') as f:
            f.write(yaml.dump(self.__trees, default_flow_style=False))
