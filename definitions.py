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


class Definitions(object):

    def __init__(self):
        '''Load all definitions from `cwd` tree.'''
        self._definitions = {}
        self._trees = {}

        json_schema = self._load(app.settings.get('json-schema'))
        definitions_schema = self._load(app.settings.get('defs-schema'))
        if json_schema and definitions_schema:
            import jsonschema as js
            js.validate(json_schema, json_schema)
            js.validate(definitions_schema, json_schema)

        things_have_changed = not self._check_trees()
        for dirname, dirnames, filenames in os.walk('.'):
            filenames.sort()
            dirnames.sort()
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
            for name in self._definitions:
                self._definitions[name]['tree'] = self._trees.get(name)

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

    def _tidy(self, definition):
        '''Insert a definition and its contents into the dictionary.

        Takes a dict containing the content of a definition file.

        Inserts the definitions references or defined in the
        'build-dependencies' and 'contents' keys of `definition` into
        the dictionary, and then inserts `definition` itself into the
        dictionary.

        '''
        self._fix_path_name(definition)

        # handle morph syntax oddities...
        def fix_path_names(system):
            self._fix_path_name(system)
            for subsystem in system.get('subsystems', []):
                fix_path_names(subsystem)

        for system in definition.get('systems', []):
            fix_path_names(system)

        for index, component in enumerate(
                definition.get('build-depends', [])):
            self._fix_path_name(component)
            definition['build-depends'][index] = self._insert(component)

        for subset in ['chunks', 'strata']:
            if subset in definition:
                definition['contents'] = definition.pop(subset)

        lookup = {}
        for index, component in enumerate(definition.get('contents', [])):
            self._fix_path_name(component)
            lookup[component['name']] = component['path']
            if component['name'] == definition['name']:
                app.log(definition,
                        'WARNING: %s contains' % definition['name'],
                        component['name'])
            for x, it in enumerate(component.get('build-depends', [])):
                component['build-depends'][x] = lookup.get(it, it)

            component['build-depends'] = (
                definition.get('build-depends', []) +
                component.get('build-depends', [])
            )
            definition['contents'][index] = self._insert(component)

        return self._insert(definition)

    def _fix_path_name(self, definition, name='ERROR'):
        if definition.get('path', None) is None:
            definition['path'] = definition.pop('morph',
                                                definition.get('name', name))
            if definition['path'] == 'ERROR':
                app.exit(definition, 'ERROR: no path, no name?')
        if definition.get('name') is None:
            definition['name'] = definition['path'].replace('/', '-')
        if definition['name'] == app.settings['target']:
            app.settings['target'] = definition['path']

    def _insert(self, new_def):
        '''Insert a new definition into the dictionary, return the key.

        Takes a dict representing a single definition.

        If a definition with the same 'path' already exists, extend the
        existing definition with the contents of `new_def` unless it
        and the new definition contain a 'ref'. If any keys are
        duplicated in the existing definition, output a warning.

        If a definition with the same 'path' doesn't exist, just add
        `new_def` to the dictionary.

        '''
        definition = self._definitions.get(new_def['path'])
        if definition:
            if (definition.get('ref') is None or new_def.get('ref') is None):
                for key in new_def:
                    definition[key] = new_def[key]

            for key in new_def:
                if definition.get(key) != new_def[key]:
                    app.log(new_def, 'WARNING: multiple definitions of', key)
                    app.log(new_def,
                            '%s | %s' % (definition.get(key), new_def[key]))
        else:
            self._definitions[new_def['path']] = new_def

        return new_def['path']

    def get(self, definition):
        '''Return a definition from the dictionary.

        If `definition` is a string, return the definition with that
        key.

        If `definition` is a dict, return the definition with key equal
        to the 'path' value in the given dict.

        '''
        if type(definition) is str:
            return self._definitions.get(definition)

        return self._definitions.get(definition['path'])

    def _check_trees(self):
        try:
            with app.chdir(app.settings['defdir']):
                checksum = check_output('ls -lRA */', shell=True)
            checksum = hashlib.md5(checksum).hexdigest()
            with open('.trees') as f:
                text = f.read()
            self._trees = yaml.safe_load(text)
            if self._trees.get('.checksum') == checksum:
                return True
        except:
            if os.path.exists('.trees'):
                os.remove('.trees')
            self._trees = {}
            return False

    def save_trees(self):
        with app.chdir(app.settings['defdir']):
            checksum = check_output('ls -lRA */', shell=True)
        checksum = hashlib.md5(checksum).hexdigest()
        self._trees = {'.checksum': checksum}
        for name in self._definitions:
            if self._definitions[name].get('tree') is not None:
                self._trees[name] = self._definitions[name]['tree']

        with open(os.path.join(os.getcwd(), '.trees'), 'w') as f:
            f.write(yaml.dump(self._trees, default_flow_style=False))
