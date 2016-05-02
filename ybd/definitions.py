# Copyright (C) 2014-2016  Codethink Limited
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

import json
import yaml
import os
import app
import cache
from subprocess import check_output, PIPE
import hashlib
from defaults import Defaults
import jsonschema


class Definitions(object):

    def __init__(self, directory='.'):
        '''Load all definitions from a directory tree.'''
        self._data = {}
        self._trees = {}
        self.defaults = Defaults()
        app.config['cpu'] = self.defaults.cpus.get(app.config['arch'],
                                                   app.config['arch'])

        schemas = self.load_schemas()
        with app.chdir(directory):
            for dirname, dirnames, filenames in os.walk('.'):
                filenames.sort()
                dirnames.sort()
                if '.git' in dirnames:
                    dirnames.remove('.git')
                for filename in filenames:
                    if filename.endswith(('.def', '.morph')):
                        path = os.path.join(dirname, filename)
                        data = self._load(path)
                        if data is not None:
                            self.validate_schema(schemas, data)
                            data['path'] = path[2:]
                            self._fix_keys(data)
                            self._tidy_and_insert_recursively(data)

        caches_are_valid = self._check_trees()
        for path in self._data:
            try:
                this = self._data[path]
                if this.get('ref') and self._trees.get(path):
                    if this['ref'] == self._trees.get(path)[0]:
                        this['tree'] = self._trees.get(path)[1]
            except:
                app.log('DEFINITIONS', 'WARNING: problem with .trees file')
                pass

        if app.config.get('mode') == 'parse-only':
            with open(app.config['result-file'], 'w') as f:
                f.write(json.dumps(self._data, indent=4,
                                   sort_keys=True))
            app.log('RESULT', 'Parsed definitions data in json format is at',
                    app.config['result-file'])
            os._exit(0)

    def load_schemas(self):
        app.log('SCHEMAS', 'Validation is',
                app.config.get('schema-validation', 'off'))
        return {x: self._load(app.config['schemas'][x])
                for x in app.config.get('schemas')}

    def validate_schema(self, schemas, data):
        if schemas == {} or \
                app.config.get('schema-validation', False) is False:
            return
        try:
            jsonschema.validate(data, schemas[data.get('kind', None)])
        except jsonschema.exceptions.ValidationError as e:
            if app.config.get('schema-validation') == 'strict':
                app.exit(data, 'ERROR: schema validation failed:\n', e)

            app.log(data, 'WARNING: schema validation failed:')
            print e

    def write(self, output):
        for path in self._data:
            print path
        for path in self._data:
            filename = self._data[path]['name'] + '.cida'
            with open(os.path.join(output, filename), 'w') as f:
                f.write(yaml.dump(self._data[path],
                        default_flow_style=False))

    def _load(self, path):
        '''Load a single definition file as a dict.

        The file is assumed to be yaml, and we insert the provided path into
        the dict keyed as 'path'.

        '''
        try:
            with open(path) as f:
                text = f.read()
            contents = yaml.safe_load(text)
        except yaml.YAMLError, exc:
            app.log('DEFINITIONS', 'WARNING: Error parsing %s' % path, exc)
            return None
        except:
            app.log('DEFINITIONS', 'WARNING: Unexpected error loading', path)
            return None

        if type(contents) is not dict:
            app.log('DEFINITIONS', 'WARNING: %s contents is not dict:' % path,
                    str(contents)[0:50])
            return None
        return contents

    def _tidy_and_insert_recursively(self, item):
        '''Insert a definition and its contents into the dictionary.

        Takes a dict containing the content of a definition file.

        Inserts the definitions referenced or defined in the
        'build-depends' and 'contents' keys of `definition` into the
        dictionary, and then inserts `definition` itself into the
        dictionary.

        '''
        # handle morph syntax oddities...
        for index, component in enumerate(item.get('build-depends', [])):
            self._fix_keys(component)
            item['build-depends'][index] = self._insert(component)

        # The 'contents' field in the internal data model corresponds to the
        # 'chunks' field in a stratum .morph file, or the 'strata' field in a
        # system .morph file.
        item['contents'] = item.get('contents', [])
        for subset in ['chunks', 'strata']:
            for component in item.get(subset, []):
                item['contents'] += [component]

        lookup = {}
        for index, component in enumerate(item.get('contents', [])):
            self._fix_keys(component)
            lookup[component['name']] = component['path']
            if component['name'] == item['name']:
                app.log(item, 'WARNING: %s contains' % item['path'],
                        component['name'])
            for x, it in enumerate(component.get('build-depends', [])):
                component['build-depends'][x] = lookup.get(it, it)

            component['build-depends'] = (
                item.get('build-depends', []) +
                component.get('build-depends', [])
            )
            item['contents'][index] = self._insert(component)

        return self._insert(item)

    def _fix_keys(self, item, name='ERROR'):
        '''Normalizes keys for a definition dict and its contents

        Some definitions have a 'morph' field which is a relative path. Others
        only have a 'name' field, which has no directory part. A few do not
        have a 'name'

        This sets our key to be 'path', and fixes any missed 'name' to be
        the same as 'path' but replacing '/' by '-'

        '''
        item.setdefault('path', item.pop('morph', item.get('name', name)))
        if item['path'] == 'ERROR':
            app.exit(item, 'ERROR: no path, no name?')
        item.setdefault('name', item['path'])
        item['name'] = item['name'].replace('/', '-')
        if item['name'] == app.config['target']:
            app.config['target'] = item['path']

        for system in (item.get('systems', []) + item.get('subsystems', [])):
            self._fix_keys(system)

    def _insert(self, new_def):
        '''Insert a new definition into the dictionary, return the key.

        Takes a dict representing a single definition.

        If a definition with the same 'path' doesn't exist, just add
        `new_def` to the dictionary.

        If a definition with the same 'path' already exists, extend the
        existing definition with the contents of `new_def` unless it
        and the new definition both contain a 'ref'. If any keys are
        duplicated in the existing definition, output a warning.

        '''
        item = self._data.get(new_def['path'])
        if item:
            if (item.get('ref') is None or new_def.get('ref') is None):
                for key in new_def:
                    item[key] = new_def[key]

            for key in new_def:
                if item.get(key) != new_def[key]:
                    app.log(new_def, 'WARNING: multiple definitions of', key)
                    app.log(new_def, '%s | %s' % (item.get(key), new_def[key]))
        else:
            self._data[new_def['path']] = new_def

        return new_def['path']

    def get(self, item):
        '''Return a definition from the dictionary.

        If `item` is a string, return the definition with that key.

        If `item` is a dict, return the definition with key equal
        to the 'path' value in the given dict.

        '''
        if type(item) is str:
            return self._data.get(item)

        return self._data.get(item['path'])

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
            self._trees = {}

        return False

    def save_trees(self):
        '''Creates the .trees file for the current working directory

        .trees contains a list of git trees for all the definitions, and a
        checksum for the state of the working subdirectories
        '''
        with app.chdir(app.config['defdir']):
            try:
                checksum = check_output('ls -lRA */', shell=True)
            except:
                checksum = check_output('ls -lRA .', shell=True)
        checksum = hashlib.md5(checksum).hexdigest()
        self._trees = {'.checksum': checksum}
        for name in self._data:
            if self._data[name].get('tree') is not None:
                self._trees[name] = [self._data[name]['ref'],
                                     self._data[name]['tree'],
                                     self._data[name].get('cache')]

        with open(os.path.join(os.getcwd(), '.trees'), 'w') as f:
            f.write(yaml.safe_dump(self._trees, default_flow_style=False))
