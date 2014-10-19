#!/usr/bin/python
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
import hashlib
import app


def get(thing, value):
    ''' Look up value from thing, return thing if none. '''
    val = []
    try:
        val = thing[value]
    except:
        pass
    return val


def load_defs(path, definitions):
    ''' Load all definitions from `cwd` tree. '''
    for dirname, dirnames, filenames in os.walk("."):
        for filename in filenames:
            if not (filename.endswith('.def') or
                    filename.endswith('.morph')):
                continue

            this = load_def(dirname, filename)
#            log(this, 'loading definition')
            name = get(this, 'name')
            if name != []:
                for i, definition in enumerate(definitions):
                    if definition['name'] == this['name']:
                        for key in this:
                            definitions[i][key] = this[key]

                if get(definitions, 'name') == []:
                    definitions.append(this)

                for dependency in get(this, 'build-depends'):
                    # print 'dependency is %s' % dependency
                    if get(dependency, 'repo') != []:
                        dependency['hash'] = this['hash']
                        definitions.append(dependency)

                for content in get(this, 'contents'):
                    # print 'content is %s' % content
                    if get(content, 'repo') != []:
                        content['hash'] = this['hash']
                        definitions.append(content)

        if '.git' in dirnames:
            dirnames.remove('.git')


def load_def(path, name):
    ''' Load a single definition file, and create a hash for it. '''
    try:
        filename = os.path.join(path, name)
        with open(filename) as f:
            text = f.read()

        definition = yaml.safe_load(text)
        definition['hash'] = hashlib.sha256(filename).hexdigest()[:8]

    except ValueError:
        app.log(this, 'Oops, problem loading', filename)

    return definition


def get_def(definitions, this):
    ''' Load in the actual definition for a given named component.

    We may need to loop through the whole list to find the right entry.

    '''
    if (get(this, 'contents') != [] or get(this, 'repo') != []):
        return this

    for definition in definitions:
        if (definition['name'] == this
            or definition['name'].split('|')[0] == this
            or definition['name'] == get(this, 'name') or
                definition['name'].split('|')[0] == get(this, 'name')):
            return definition

    app.log(this, 'Oops, where is', get(this, 'name'))
    raise SystemExit


def version(this):
    try:
        return this['name'].split('|')[1]
    except:
        return False