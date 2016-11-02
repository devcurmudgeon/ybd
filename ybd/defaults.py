#!/usr/bin/env python
# Copyright (C) 2015-2016  Codethink Limited
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


'''Defaults to be used for older Baserock Definitions.

Definitions version 7 adds a file named DEFAULTS which sets the default
build commands and default split rules for the set of definitions in that
repo.

These definitions shall be used if no DEFAULTS file is present.

'''

import os
from ybd import app
from ybd.utils import log
import yaml


class Defaults(object):

    def __init__(self):
        defaults = self._load_defaults()
        self.build_steps = defaults.get('build-steps', {})
        self.fields = defaults.get('morph-fields', {})
        self.build_systems = defaults.get('build-systems', {})
        self.split_rules = defaults.get('split-rules', {})
        self.cpus = defaults.get('cpus', {})

    def _load_defaults(self, defaults_file='./DEFAULTS'):
        '''Get defaults, either from a DEFAULTS file, or built-in defaults.'''
        ybd_defaults_file = os.path.join(os.path.dirname(__file__),
                                         app.config['defaults'])
        ybd_defaults = self._load(ybd_defaults_file, ignore_errors=True)

        defaults = self._load(defaults_file, ignore_errors=True)
        if defaults is None:
            return ybd_defaults

        for index in ybd_defaults:
            if defaults.get(index) is None or defaults.get(index) == {}:
                defaults[index] = ybd_defaults[index]

        return defaults

    def _load(self, path, ignore_errors=True):
        try:
            with open(path) as f:
                contents = yaml.safe_load(f)
        except:
            if ignore_errors:
                log('DEFAULTS', 'WARNING: problem loading', path)
                return None
            else:
                raise
        contents['path'] = path[2:]
        return contents

    def get_split_rules(self, kind):
        return self.split_rules.get(kind, {})

    def lookup_build_system(self, name, default=None):
        '''Return build system that corresponds to the name.

        If the name does not match any build system, raise ``KeyError``.
        '''

        if name in self.build_systems:
            return self.build_systems[name]
        elif default:
            return default

        raise KeyError("Undefined build-system %s" % name)

    def detect_build_system(self, file_list):
        '''Automatically detect the build system, if possible.'''

        for build_system in sorted(self.build_systems):
            indicators = self.build_systems[build_system].get('indicators', [])
            if any(x in file_list for x in indicators):
                return build_system

        for build_system in sorted(self.build_systems):
            indicators = self.build_systems[build_system].get('indicators', [])
            for indicator in indicators:
                if any(x.endswith(indicator) for x in file_list):
                    return build_system

        return 'manual'
