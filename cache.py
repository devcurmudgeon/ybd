#!/usr/bin/env python3
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
import re
from subprocess import call
from subprocess import check_output
from subprocess import DEVNULL
import hashlib
import urllib.request
import json
import definitions


def cache_key(this):
    defs = definitions.Definitions()
    definition = defs.get(this)

    if defs.lookup(definition, 'cache') != []:
        return definition['cache']

    safename = definition['name'].replace('/', '-')
    hash_this = {}

    for key in ['tree', 'configure-commands', 'build-commands',
                'install-commands']:

        if defs.lookup(definition, key) != []:
            hash_this[key] = definition[key]

    for key in ['build-depends', 'components']:
        for it in defs.lookup(definition, key):
            component = defs.get(it)
            hash_this[component['name']] = cache_key(component)

    result = json.dumps(hash_this, sort_keys=True).encode('utf-8')

    definition['cache'] = safename + ":" + hashlib.sha256(result).hexdigest()
    return definition['cache']


def cache(this):
    ''' Just create an empty file for now. '''
    cachefile = os.path.join(app.config['caches'],
                             cache_key(this))
    touch(cachefile)
    app.log(this, 'is now cached at', cachefile)


def is_cached(this):
    ''' Check if a cached artifact exists for the hashed version of this. '''

    cachefile = os.path.join(app.config['caches'],
                             cache_key(this))

    if os.path.exists(cachefile):
        return cachefile

    return False


def get_repo_url(this):
    url = this['repo']
    url = url.replace('upstream:', 'git://git.baserock.org/delta/')
    url = url.replace('baserock:baserock/',
                      'git://git.baserock.org/baserock/baserock/')
    url = url.replace('freedesktop:', 'git://anongit.freedesktop.org/')
    url = url.replace('github:', 'git://github.com/')
    url = url.replace('gnome:', 'git://git.gnome.org')
    url = url + '.git'
    return url


def get_repo_name(this):
    return re.split('[:/]', this['repo'])[-1]


def get_tree(this):
    tree = None
    defs = definitions.Definitions()
    if defs.version(this):
        ref = defs.version(this)

    if defs.lookup(this, 'ref'):
        ref = defs.lookup(this, 'ref')

    url = (app.config['cache-server-url']
           + 'repo=' + get_repo_url(this) + '&ref=' + ref)

    try:
        with urllib.request.urlopen(url) as response:
            tree = json.loads(response.read().decode())['tree']

        return tree

    except:
        app.log(this, 'Cache-server does not have tree for ref', ref)

    with app.chdir(this['git']):
        try:
            if call(['git', 'rev-parse', ref + '^{object}'],
                    stdout=DEVNULL,
                    stderr=DEVNULL):
                # can't resolve this ref. is it upstream?
                call(['git', 'fetch', 'origin'],
                     stdout=DEVNULL,
                     stderr=DEVNULL)
                if call(['git', 'rev-parse', ref + '^{object}'],
                        stdout=DEVNULL,
                        stderr=DEVNULL):
                    app.log(this, 'ref is either not unique or missing', ref)
                    raise SystemExit

            tree = check_output(['git', 'rev-parse', ref + '^{tree}'],
                                universal_newlines=True)[0:-1]

        except:
            # either we don't have a git dir, or ref is not unique
            # or ref does not exist

            app.log(this, 'ERROR: could not find tree for ref', ref)

    return tree


def copy_repo(repo, destdir):
    '''Copies a cached repository into a directory using cp.

    This also fixes up the repository afterwards, so that it can contain
    code etc.  It does not leave any given branch ready for use.

    '''

    # core.bare should be false so that git believes work trees are possible
    # we do not want the origin remote to behave as a mirror for pulls
    # we want a traditional refs/heads -> refs/remotes/origin ref mapping
    # set the origin url to the cached repo so that we can quickly clean up
    # by packing the refs, we can then edit then en-masse easily
    call(['cp', '-a', repo, os.path.join(destdir, '.git')])
    call(['git', 'config', 'core.bare', 'false'])
    call(['git', 'config', '--unset', 'remote.origin.mirror'])
    call(['git', 'config', 'remote.origin.fetch',
          '+refs/heads/*:refs/remotes/origin/*'],
         stdout=DEVNULL,
         stderr=DEVNULL)
    call(['git',  'config', 'remote.origin.url', repo])
    call(['git',  'pack-refs', '--all', '--prune'])

    # turn refs/heads/* into refs/remotes/origin/* in the packed refs
    # so that the new copy behaves more like a traditional clone.
    with open(os.path.join(destdir, ".git", "packed-refs"), "r") as ref_fh:
        pack_lines = ref_fh.read().split("\n")
    with open(os.path.join(destdir, ".git", "packed-refs"), "w") as ref_fh:
        ref_fh.write(pack_lines.pop(0) + "\n")
        for refline in pack_lines:
            if ' refs/remotes/' in refline:
                continue
            if ' refs/heads/' in refline:
                sha, ref = refline[:40], refline[41:]
                if ref.startswith("refs/heads/"):
                    ref = "refs/remotes/origin/" + ref[11:]
                refline = "%s %s" % (sha, ref)
            ref_fh.write("%s\n" % (refline))
    # Finally run a remote update to clear up the refs ready for use.
    call(['git', 'remote', 'update', 'origin', '--prune'],
         stdout=DEVNULL,
         stderr=DEVNULL)


def checkout(this):
    # checkout the required version of this from git
    defs = definitions.Definitions()
    this['git'] = os.path.join(app.config['gits'], get_repo_name(this))
    if not os.path.exists(this['git']):
        # TODO - try tarball first

        if call(['git', 'clone', '--mirror', '-n', get_repo_url(this),
                 this['git']]) != 0:

            app.log(this, 'ERROR: failed to clone', get_repo_name(this))
            raise SystemExit

        app.log(this, 'git repo is mirrored at', this['git'])

    with app.chdir(this['build']):
        this['tree'] = get_tree(this)
        copy_repo(this['git'], this['build'])
        if call(['git', 'checkout', '-b', this['tree']],
                stdout=DEVNULL,
                stderr=DEVNULL) != 0:
            app.log(this, 'ERROR: git checkout failed for', this['tree'])
            raise SystemExit


def touch(pathname):
    ''' Create an empty file if pathname does not exist already. '''

    with open(pathname, 'w'):
        pass
