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
import defaults


class Definitions(object):

    def __init__(self):
        '''Load all definitions from `cwd` tree.'''
        self._definitions = {}
        self._trees = {}

        json_schema = self._load(app.config.get('json-schema'))
        definitions_schema = self._load(app.config.get('defs-schema'))
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
                    definition_data = self._load(
                        os.path.join(dirname, filename))
                    if definition_data is not None:
                        if things_have_changed and definitions_schema:
                            app.log(filename, 'Validating schema')
                            js.validate(definition_data, definitions_schema)
                        self._tidy_and_insert_recursively(definition_data)

        self.defaults = defaults.Defaults()

        if self._check_trees():
            for name in self._definitions:
                self._definitions[name]['tree'] = self._trees.get(name)

    def _load(self, path):
        '''Load a single definition file as a dict.

        The file is assumed to be yaml, and we insert the provided path into
        the dict keyed as 'path'.

        '''
        try:
            with open(path) as f:
                text = f.read()
            contents = yaml.safe_load(text)
        except:
            app.log('DEFINITIONS', 'WARNING: problem loading', path)
            return None
        contents['path'] = path[2:]
        return contents

    def _tidy_and_insert_recursively(self, definition):
        '''Insert a definition and its contents into the dictionary.

        Takes a dict containing the content of a definition file.

        Inserts the definitions referenced or defined in the
        'build-dependencies' and 'contents' keys of `definition` into the
        dictionary, and then inserts `definition` itself into the
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

        # The 'contents' field in the internal data model corresponds to the
        # 'chunks' field in a stratum .morph file, or the 'strata' field in a
        # system .morph file.
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
        '''Standardises the key for a definition

        Some definitions have a 'morph' key which is a relative path. Others
        only have a 'name' key, which has no directory part.

        This sets our key to be 'path', and fixes 'name' to be the same as
        'path' but replacing '/' by '-'

        '''
        if definition.get('path', None) is None:
            definition['path'] = definition.pop('morph',
                                                definition.get('name', name))
            if definition['path'] == 'ERROR':
                app.exit(definition, 'ERROR: no path, no name?')
        if definition.get('name') is None:
            definition['name'] = definition['path'].replace('/', '-')
        if definition['name'] == app.config['target']:
            app.config['target'] = definition['path']

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

        If `definition` is a string, return the definition with that key.

        If `definition` is a dict, return the definition with key equal
        to the 'path' value in the given dict.

        '''
        if type(definition) is str:
            return self._definitions.get(definition)

        return self._definitions.get(definition['path'])


    def set_member(self, definition, member, value):
        '''Set a member in the dictionary.'''

        if self._definitions.get(definition, None):
            self._definitions[definition][member] = value


    def _check_trees(self):
        '''True if the .trees file matches the current working subdirectories

        The .trees file lists all git trees for a set of definitions, and a
        checksum of the checked-out subdirectories when we calculated them.

        If the checksum for the current subdirectories matches, return True

        '''
        try:
            with app.chdir(app.config['defdir']):
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
        '''Creates the .trees file for the current working directory

        .trees contains a list of git trees for all the definitions, and a
        checksum for the state of the working subdirectories
        '''
        with app.chdir(app.config['defdir']):
            checksum = check_output('ls -lRA */', shell=True)
        checksum = hashlib.md5(checksum).hexdigest()
        self._trees = {'.checksum': checksum}
        for name in self._definitions:
            if self._definitions[name].get('tree') is not None:
                self._trees[name] = self._definitions[name]['tree']

        with open(os.path.join(os.getcwd(), '.trees'), 'w') as f:
            f.write(yaml.dump(self._trees, default_flow_style=False))
