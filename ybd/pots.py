# Copyright (C) 2016  Codethink Limited
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

import os
import yaml
from app import config, log
from defaults import Defaults
from morphs import Morphs


# copied from http://stackoverflow.com/questions/21016220
class ExplicitDumper(yaml.SafeDumper):
    """
    A dumper that will never emit aliases.
    """

    def ignore_aliases(self, data):
        return True


class Pots(object):

    def __init__(self, directory='.'):
        self._data = Morphs()._data
        self._trees = {}
        self._set_trees()
        self.defaults = Defaults()
        self._save_pots('./definitions.yml')

    def get(self, dn):
        ''' Return a definition from the dictionary.

        If `dn` is a string, return the definition with that key.
        If `dn` is a dict, return the definition with key equal to the 'path'
        value in the given dict. '''

        if type(dn) is str:
            if self._data.get(dn):
                return self._data.get(dn)
            log(dn, 'Unable to find definition for', dn, exit=True)

        return self._data.get(dn.get('path', dn.keys()[0]))

    def _save_pots(self, filename):
        with open(filename, 'w') as f:
            f.write(yaml.dump(self._data, default_flow_style=False,
                              Dumper=ExplicitDumper))
        log('RESULT', 'Saved yaml definitions at', filename)

    def _load_pots(self, filename):
        with open(filename) as f:
            text = f.read()
        return yaml.safe_load(text)

    def _set_trees(self):
        '''Use the tree values from .trees file, to save time'''
        try:
            with open(os.path.join(config['artifacts'], '.trees')) as f:
                text = f.read()
                self._trees = yaml.safe_load(text)
            for path in self._data:
                dn = self._data[path]
                if dn.get('ref') and self._trees.get(path):
                    if dn['ref'] == self._trees.get(path)[0]:
                        dn['tree'] = self._trees.get(path)[1]
        except:
            log('DEFINITIONS', 'WARNING: problem with .trees file')
            pass

    def save_trees(self):
        '''Creates the .trees file for the current working directory

        .trees contains lookups of git trees from git refs for all definitions
        '''
        for name in self._data:
            if self._data[name].get('tree') is not None:
                self._trees[name] = [self._data[name]['ref'],
                                     self._data[name]['tree'],
                                     self._data[name].get('cache')]
        with open(os.path.join(config['artifacts'], '.trees'), 'w') as f:
            f.write(yaml.safe_dump(self._trees, default_flow_style=False))
