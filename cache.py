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
from subprocess import check_output


def cache_key(definitions, this):
    ''' A simple cache key. May not be safe, yet. '''
    # what about architecture?

    definition = defs.get_def(definitions, this)
    return (definition['name'] + "|" +
            definition['hash'] + ".cache")


def cache(definitions, this):
    ''' Just create an empty file for now. '''
    cachefile = os.path.join(app.config['caches'],
                             cache_key(definitions, this))
    touch(cachefile)
    app.log('is now cached at', this, cachefile)


def is_cached(definitions, this):
    ''' Check if a cached artifact exists for the hashed version of this. '''
    cachefile = os.path.join(app.config['caches'],
                             cache_key(definitions, this))
    if os.path.exists(cachefile):
        return cachefile

    return False


def get_sha(this):
    if defs.version(this):
        ref = defs.version(this)

    if this['ref']:
        ref = this['ref']

    os.chdir(this['git'])
    sha1 = check_output(['git', 'rev-parse', ref])[0:-1]

    return sha1


def get_tree(this):

    try:
        os.chdir(this['git'])
        call(['pwd'])
        app.log('ref is', this, get_ref(this))
        tree = check_output(['git', 'rev-parse', get_ref(this) + '^{tree}'])[0:-1]
        app.log('tree is', this, tree)

    except:
        app.log('something went wrong', this, get_ref(this))
        raise SystemExit
        # either we don't have a git dir, or ref is not unique, or does not exist
        try:
            refs = call(['git', 'rev-list', '--all'])
            print refs[-1]

        except:
            pass

    return tree


def checkout(this):
    # checkout the required version of this from git
    if this['repo']:
        repo = this['repo'].replace('upstream:','')
        this['git'] = os.path.join(app.config['gits'], repo)
        if not os.path.exists(this['git']):
            # TODO - try tarball first
            call(['git', 'clone', 'git://git.baserock.org/delta/' + repo + '.git', this['git']])

        app.log('git repo is mirrored at', this, this['git'])

        # if we don't have the required ref, try to fetch it?
        builddir = os.path.join(app.config['assembly'], this['name'] +'.build')
        call(['git', 'clone', this['git'], builddir])
        os.chdir(builddir)
        sha = get_sha(this)
        if call(['git', 'checkout', sha]) != 0:
            app.log('Oops, git checkout failed for ', this, get_sha(this))
            raise SystemExit

#    else:
#        # this may be a tarball
#        app.log('No repo specified for', this)
#        raise SystemExit

    return builddir


def touch(pathname):
    ''' Create an empty file if pathname does not exist already. '''
    with open(pathname, 'w'):
        pass