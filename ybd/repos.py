# Copyright (C) 2011-2016  Codethink Limited
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
import re
import shutil
import string
from subprocess import call, check_output
import sys
import requests
import app
import utils
import tempfile


if sys.version_info.major == 2:
    # For compatibility with Python 2.
    from ConfigParser import RawConfigParser
    from StringIO import StringIO
else:
    from configparser import RawConfigParser
    from io import StringIO


def get_repo_url(repo):
    if repo:
        for alias, url in app.config.get('aliases', {}).items():
            repo = repo.replace(alias, url)
        if repo[:4] == "http" and not repo.endswith('.git'):
            repo = repo + '.git'
    return repo


def get_repo_name(repo):
    ''' Convert URIs to strings that only contain digits, letters, _ and %.

    NOTE: this naming scheme is based on what lorry uses

    '''
    def transl(x):
        return x if x in valid_chars else '_'

    valid_chars = string.digits + string.ascii_letters + '%_'
    url = get_repo_url(repo)
    if url.endswith('.git'):
        url = url[:-4]
    return ''.join([transl(x) for x in url])


def get_version(gitdir, ref='HEAD'):
    try:
        with app.chdir(gitdir), open(os.devnull, "w") as fnull:
            version = check_output(['git', 'describe', '--tags', '--dirty'],
                                   stderr=fnull)[0:-1]
            tag = check_output(['git', 'describe', '--abbrev=0',
                                '--tags', ref], stderr=fnull)[0:-1]
            commits = check_output(['git', 'rev-list', tag + '..' + ref,
                                    '--count'])[0:-1]
        result = "%s %s (%s + %s commits)" % (ref[:8], version, tag, commits)
    except:
        result = ref[:8] + " (No tag found)"

    return result


def get_last_tag(gitdir):
    try:
        with app.chdir(gitdir), open(os.devnull, "w") as fnull:
            tag = check_output(['git', 'describe', '--abbrev=0',
                                '--tags', ref], stderr=fnull)[0:-1]
        return tag
    except:
        return None


def get_tree(dn):
    ref = dn['ref']
    gitdir = os.path.join(app.config['gits'], get_repo_name(dn['repo']))
    if dn['repo'].startswith('file://') or dn['repo'].startswith('/'):
        gitdir = dn['repo'].replace('file://', '')
        if not os.path.isdir(gitdir):
            app.exit(dn, 'ERROR: git repo not found:', dn['repo'])

    if not os.path.exists(gitdir):
        try:
            params = {'repo': get_repo_url(dn['repo']), 'ref': ref}
            r = requests.get(url=app.config['tree-server'], params=params)
            return r.json()['tree']
        except:
            if app.config.get('tree-server'):
                app.log(dn, 'WARNING: no tree from tree-server for', ref)

        mirror(dn['name'], dn['repo'])

    with app.chdir(gitdir), open(os.devnull, "w") as fnull:
        if call(['git', 'rev-parse', ref + '^{object}'], stdout=fnull,
                stderr=fnull):
            # can't resolve ref. is it upstream?
            app.log(dn, 'Fetching from upstream to resolve %s' % ref)
            update_mirror(dn['name'], dn['repo'], gitdir)

        try:
            tree = check_output(['git', 'rev-parse', ref + '^{tree}'],
                                universal_newlines=True)[0:-1]
            return tree

        except:
            # either we don't have a git dir, or ref is not unique
            # or ref does not exist
            app.exit(dn, 'ERROR: could not find tree for ref', (ref, gitdir))


def mirror(name, repo):
    tempfile.tempdir = app.config['tmp']
    tmpdir = tempfile.mkdtemp()
    repo_url = get_repo_url(repo)
    try:
        tar_file = get_repo_name(repo_url) + '.tar'
        app.log(name, 'Try fetching tarball %s' % tar_file)
        # try tarball first
        with app.chdir(tmpdir), open(os.devnull, "w") as fnull:
            call(['wget', os.path.join(app.config['tar-url'], tar_file)])
            call(['tar', 'xf', tar_file], stderr=fnull)
            os.remove(tar_file)
            update_mirror(name, repo, tmpdir)
    except:
        app.log(name, 'Try git clone from', repo_url)
        with open(os.devnull, "w") as fnull:
            if call(['git', 'clone', '--mirror', '-n', repo_url, tmpdir]):
                app.exit(name, 'ERROR: failed to clone', repo)

    with app.chdir(tmpdir):
        if call(['git', 'rev-parse']):
            app.exit(name, 'ERROR: problem mirroring git repo at', tmpdir)

    gitdir = os.path.join(app.config['gits'], get_repo_name(repo))
    try:
        shutil.move(tmpdir, gitdir)
        app.log(name, 'Git repo is mirrored at', gitdir)
    except:
        pass


def fetch(repo):
    with app.chdir(repo), open(os.devnull, "w") as fnull:
        call(['git', 'fetch', 'origin'], stdout=fnull, stderr=fnull)


def mirror_has_ref(gitdir, ref):
    with app.chdir(gitdir), open(os.devnull, "w") as fnull:
        out = call(['git', 'cat-file', '-t', ref], stdout=fnull, stderr=fnull)
        return out == 0


def update_mirror(name, repo, gitdir):
    with app.chdir(gitdir), open(os.devnull, "w") as fnull:
        app.log(name, 'Refreshing mirror for %s' % repo)
        repo_url = get_repo_url(repo)
        if call(['git', 'fetch', repo_url, '+refs/*:refs/*', '--prune'],
                stdout=fnull, stderr=fnull):
            app.exit(name, 'ERROR: git update mirror failed', repo)


def checkout(dn):
    _checkout(dn['name'], dn['repo'], dn['ref'], dn['build'])

    with app.chdir(dn['build']):
        if os.path.exists('.gitmodules') or dn.get('submodules'):
            checkout_submodules(dn)

    utils.set_mtime_recursively(dn['build'])


def _checkout(name, repo, ref, checkout):
    gitdir = os.path.join(app.config['gits'], get_repo_name(repo))
    if not os.path.exists(gitdir):
        mirror(name, repo)
    elif not mirror_has_ref(gitdir, ref):
        update_mirror(name, repo, gitdir)
    # checkout the required version from git
    with open(os.devnull, "w") as fnull:
        # We need to pass '--no-hardlinks' because right now there's nothing to
        # stop the build from overwriting the files in the .git directory
        # inside the sandbox. If they were hardlinks, it'd be possible for a
        # build to corrupt the repo cache. I think it would be faster if we
        # removed --no-hardlinks, though.
        if call(['git', 'clone', '--no-hardlinks', gitdir, checkout],
                stdout=fnull, stderr=fnull):
            app.exit(name, 'ERROR: git clone failed for', ref)

        with app.chdir(checkout):
            if call(['git', 'checkout', '--force', ref], stdout=fnull,
                    stderr=fnull):
                app.exit(name, 'ERROR: git checkout failed for', ref)

            app.log(name, 'Git checkout %s in %s' % (repo, checkout))
            app.log(name, 'Upstream version %s' % get_version(checkout, ref))


def source_date_epoch(checkout):
    with app.chdir(checkout):
        return check_output(['git', 'log', '-1', '--pretty=%ct'])[:-1]


def run(args, dir='.'):
    with app.chdir(dir), open(os.devnull, "w") as fnull:
        ret = call(['git'] + args)


def extract_commit(name, repo, ref, target_dir):
    '''Check out a single commit (or tree) from a Git repo.
    The checkout() function actually clones the entire repo, so this
    function is much quicker when you don't need to copy the whole repo into
    target_dir.
    '''
    gitdir = os.path.join(app.config['gits'], get_repo_name(repo))
    if not os.path.exists(gitdir):
        mirror(name, repo)
    elif not mirror_has_ref(gitdir, ref):
        update_mirror(name, repo, gitdir)

    with tempfile.NamedTemporaryFile() as git_index_file:
        git_env = os.environ.copy()
        git_env['GIT_INDEX_FILE'] = git_index_file.name
        git_env['GIT_WORK_TREE'] = target_dir

        app.log(name, 'Extracting commit', ref)
        if call(['git', 'read-tree', ref], env=git_env, cwd=gitdir):
            app.exit(name, 'ERROR: git read-tree failed for', ref)
        app.log(name, 'Then checkout index', ref)
        if call(['git', 'checkout-index', '--all'], env=git_env, cwd=gitdir):
            app.exit(name, 'ERROR: git checkout-index failed for', ref)
        app.log(name, 'Done', ref)

    utils.set_mtime_recursively(target_dir)


def checkout_submodules(dn):
    app.log(dn, 'Checking git submodules')
    with open('.gitmodules', "r") as gitfile:
        # drop indentation in sections, as RawConfigParser cannot handle it
        content = '\n'.join([l.strip() for l in gitfile.read().splitlines()])
    io = StringIO(content)
    parser = RawConfigParser()
    parser.readfp(io)

    for section in parser.sections():
        # validate section name against the 'submodule "foo"' pattern
        submodule = re.sub(r'submodule "(.*)"', r'\1', section)
        path = parser.get(section, 'path')
        try:
            url = dn['submodules'][path]['url']
            app.log(dn, 'Processing submodule %s from' % path, url)
        except:
            url = parser.get(section, 'url')
            app.log(dn, 'WARNING: fallback to submodule %s from' % path, url)

        try:
            # list objects in the parent repo tree to find the commit
            # object that corresponds to the submodule
            commit = check_output(['git', 'ls-tree', dn['ref'], path])

            # read the commit hash from the output
            fields = commit.split()
            if len(fields) >= 2 and fields[1] == 'commit':
                submodule_commit = commit.split()[2]

                # fail if the commit hash is invalid
                if len(submodule_commit) != 40:
                    raise Exception

                fulldir = os.path.join(os.getcwd(), path)
                _checkout(dn['name'], url, submodule_commit, fulldir)

            else:
                app.log(dn, 'Skipping submodule %s, not a commit:' % path,
                        fields)

        except:
            app.exit(dn, "ERROR: git submodules problem", "")
