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

import os
import app
import defs
from subprocess import call


def cache_key(definitions, this):
    ''' A simple cache key. May not be safe, yet. '''
    # what about architecture?

    definition = defs.get_def(definitions, this)
    return (definition['name'] + "|" +
            definition['hash'] + ".cache")


def cache(definitions, this):
    ''' Just create an empty file for now. '''
    cachefile = os.path.join(app.config['cachedir'],
                             cache_key(definitions, this))
    touch(cachefile)
    app.log('is now cached at', this, cachefile)


def is_cached(definitions, this):
    ''' Check if a cached artifact exists for the hashed version of this. '''
    cachefile = os.path.join(app.config['cachedir'],
                             cache_key(definitions, this))
    if os.path.exists(cachefile):
        return cachefile

    return False


def git_tree(repo, ref):
    try:
        tree = call(['git', 'rev-parse', ref + '^{tree}'])
        print tree
    except:
        # either ref is not unique, or does not exist
        pass

    return tree


def checkout(this):
    # checkout the required version of this from git
    assemblydir = os.path.join(app.config['assembly'], this['name'])
    gitdir = os.path.join(app.config['gitdir'], this['name'])
    if this['repo']:
        if not os.path.exists(gitdir):
            call(['git', 'clone', this['repo'], gitdir])
        # if we don't have the required ref, try to fetch it?

        call(['git', 'clone', gitdir, assemblydir])
        if defs.version(this):
            call(['git', 'checkout', defs.version(this)])
        if this['ref']:
            call(['git', 'checkout', this('ref')])
    else:
        # this may be a tarball
        pass

    return assemblydir


def touch(pathname):
    ''' Create an empty file if pathname does not exist already. '''
    with open(pathname, 'w'):
        pass