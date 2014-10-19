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
import git
from subprocess import call
from subprocess import check_output


def cache_key(definitions, this):
    ''' A simple cache key. May not be safe, yet. '''
    # what about architecture?

    definition = defs.get_def(definitions, this)
    safename = definition['name'].replace('/', '-')
    return (safename + "|" +
            definition['hash'] + ".cache")


def cache(definitions, this):
    ''' Just create an empty file for now. '''
    cachefile = os.path.join(app.config['caches'],
                             cache_key(definitions, this))
    touch(cachefile)
    app.log(this, 'is now cached at', cachefile)


def is_cached(definitions, this):
    ''' Check if a cached artifact exists for the hashed version of this. '''
    cachefile = os.path.join(app.config['caches'],
                             cache_key(definitions, this))
    if os.path.exists(cachefile):
        return cachefile

    return False


def get_repo_url(this):
    url = this['repo']
    url = url.replace('upstream:', 'git://git.baserock.org/delta/')
    url = url.replace('baserock:baserock/',
                      'git://git.baserock.org/baserock/baserock/')
    url = url + '.git'
    return url


def get_repo_name(this):
    repo = this['repo']
    repo = repo.replace('upstream:', '')
    repo = repo.replace('baserock:baserock/', '')
    return repo


def get_tree(this):
    if defs.get(this, 'ref'):
        ref = defs.get(this, 'ref')

    if defs.version(this):
        ref = defs.version(this)

    with app.chdir(this['git']):
        try:
            if call(['git', 'rev-parse', ref]):
                # ref is either not unique or missing
                app.log(this, 'ref is either not unique or missing', ref)
            else:
                sha1 = check_output(['git', 'rev-parse', ref])[0:-1]
                tree = check_output(['git', 'rev-parse', sha1
                                     + '^{tree}'])[0:-1]

        except:
            # either we don't have a git dir, or ref is not unique
            # or ref does not exist

            app.log('ERROR: could not find tree for', this, ref)
            raise SystemExit
            try:
                refs = call(['git', 'rev-list', '--all'],
                            stdout=subprocess.PIPE)
                print refs[-1]

            except:
                app.log('ERROR: could not find tree for', this, ref)
                raise SystemExit

    app.log(this, 'tree is', tree)
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
          '+refs/heads/*:refs/remotes/origin/*'])
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
    call(['git', 'remote', 'update', 'origin', '--prune'])


def checkout(this):
    # checkout the required version of this from git
    if defs.get(this, 'repo'):
        this['git'] = os.path.join(app.config['gits'], get_repo_name(this))
        if not os.path.exists(this['git']):
            # TODO - try tarball first

            if call(['git', 'clone', '--mirror', '-n', get_repo_url(this),
                     this['git']]) != 0:

                app.log(this, 'ERROR: failed to clone', get_repo_name(this))
                raise SystemExit

        app.log(this, 'git repo is mirrored at', this['git'])

        # if we don't have the required ref, try to fetch it?

        this['build'] = os.path.join(app.config['assembly'], this['name']
                                     + '.build')

        try:
            os.makedirs(this['build'])
            with app.chdir(this['build']):
                copy_repo(this['git'], this['build'])

        except:
            app.log(this, 'Re-using existing build dir', this['build'])

        with app.chdir(this['build']):
            tree = get_tree(this)
            if call(['git', 'checkout', '-b', tree]) != 0:
                app.log(this, 'ERROR: git checkout failed for', get_tree(this))
                raise SystemExit

    else:
        # this may be a tarball, or a collection

        app.log(this, 'No repo specified')


def touch(pathname):
    ''' Create an empty file if pathname does not exist already. '''

    with open(pathname, 'w'):
        pass