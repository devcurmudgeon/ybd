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

import yaml
import os
import sys
import hashlib
import datetime


def load_defs(path, definitions):
    for dirname, dirnames, filenames in os.walk("."):
        for filename in filenames:
            if not (filename.endswith('.def') or
                    filename.endswith('.morph')):
                continue

            this = load_def(dirname, filename)
            name = get(this, 'name')
            if name != []:
                for i, definition in enumerate(definitions):
                    if definition['name'] == this['name']:
                        definitions[i] = this

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

    for i in definitions:
        print
        print i


def load_def(path, name):
    try:
        with open(path + "/" + name) as f:
            text = f.read()

        definition = yaml.safe_load(text)
        definition['hash'] = hashlib.sha256(path + "/" + name).hexdigest()[:8]

    except ValueError:
        print 'Oops, problem loading %s' % (path + "/" + name)

    return definition


def get_definition(definitions, this):
    if (get(this, 'contents') != [] or get(this, 'repo') != [] and
            get(this, 'ref') != []):
        return this

    for definition in definitions:
        if (definition['name'] == this
        or definition['name'].split('|')[0] == this
        or definition['name'] == get(this, 'name')
        or definition['name'].split('|')[0] == get(this, 'name')):
            return definition

    print "Oh dear, where is %s, %s?" % (this, get(this, 'name'))
    raise SystemExit


def get(thing, value):
    val = []
    try:
        val = thing[value]
    except:
        pass
    return val


def assemble(definitions, this):
    log('assemble', get(this, 'name'))


def touch(pathname):
    with open(pathname, 'w'):
        pass


def log(message, component='', data=''):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print '%s [%s] %s %s' % (timestamp, component, message, data)


def cache_key(definitions, this):
    definition = get_definition(definitions, this)
    # print 'cache_key %s' % definition
    return (definition['name'] + "|" +
            definition['hash'] + ".cache")


def cache(definitions, this):
    log('is cached at', get(this, 'name'), 'test-definitions/cache/'
        + cache_key(definitions, this))
    touch('test-definitions/cache/' + cache_key(definitions, this))


def is_cached(defs, this):
    if os.path.exists('test-definitions/cache/' + cache_key(defs, this)):
        return True

    return False

    for cache in maybe_caches(this):
        ref = get_ref(cache)
        diff = git_diff(DTR, ref)
        if diff:
            for dependency in this['build-depends']:
                return


def build(definitions, target):
    log('starting build', get(target, 'name'))
    if is_cached(definitions, target):
        log('is already cached', get(target, 'name'))
        return

    this = get_definition(definitions, target)

    for dependency in get(this, 'build-depends'):
        build(definitions, dependency)

    # wait here for all the dependencies to complete
    # how do we know when that happens?

    for content in get(this, 'contents'):
        build(definitions, content)

    assemble(definitions, this)
    cache(definitions, this)


definitions = []
path, target = os.path.split(sys.argv[1])
load_defs(path, definitions)
target = target.replace('.def', '')
target = target.replace('.morph', '')
build(definitions, target)
