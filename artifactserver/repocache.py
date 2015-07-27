# Copyright (C) 2013,2014-2015 Codethink Limited
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


import os
import re
import string
import urlparse


class RepoCache(object):
    
    def __init__(self, app, repo_cache_dir, bundle_cache_dir, direct_mode):
        self.app = app
        self.repo_cache_dir = repo_cache_dir
        self.bundle_cache_dir = bundle_cache_dir
        self.direct_mode = direct_mode

    def resolve_ref(self, repo_url, ref):
        quoted_url = self._quote_url(repo_url)
        repo_dir = os.path.join(self.repo_cache_dir, quoted_url)
        if not os.path.exists(repo_dir):
            repo_dir = "%s.git" % repo_dir
            if not os.path.exists(repo_dir):
                raise Exception('Repository %s does not exist in the cache' % repo)
        try:
            if re.match('^[0-9a-fA-F]{40}$', ref):
                sha1 = ref
            else:
                if (not self.direct_mode and
                    not ref.startswith('refs/origin/')):
                    ref = 'refs/origin/' + ref
                sha1 = self._rev_parse(repo_dir, ref)
            return sha1, self._tree_from_commit(repo_dir, sha1)

        except Exception:
            raise

    def _tree_from_commit(self, repo_dir, commitsha):
        commit_info = self.app.runcmd(['git', 'log', '-1',
                                       '--format=format:%T', commitsha],
                                      cwd=repo_dir)
        return commit_info.strip()

    def cat_file(self, repo_url, ref, filename):
        quoted_url = self._quote_url(repo_url)
        repo_dir = os.path.join(self.repo_cache_dir, quoted_url)
        if not os.path.exists(repo_dir):
            repo_dir = "%s.git" % repo_dir
            if not os.path.exists(repo_dir):
                raise Exception('Repository %s does not exist in the cache' % repo)
        if not self._is_valid_sha1(ref):
            raise Exception('Ref %s is not a SHA1 ref for repo %s' % (ref, repo))
        if not os.path.exists(repo_dir):
            raise Exception('Repository %s does not exist in the cache' % repo)
        try:
            sha1 = self._rev_parse(repo_dir, ref)
        except BaseException:
            raise Exception('Ref %s is an invalid reference for repo %s' % (ref, repo))

        return self._cat_file(repo_dir, sha1, filename)

    def ls_tree(self, repo_url, ref, path):
        quoted_url = self._quote_url(repo_url)
        repo_dir = os.path.join(self.repo_cache_dir, quoted_url)
        if not os.path.exists(repo_dir):
            repo_dir = "%s.git" % repo_dir
            if not os.path.exists(repo_dir):
                raise Exception('Repository %s does not exist in the cache' % repo)
        if not self._is_valid_sha1(ref):
            raise Exception('Ref %s is not a SHA1 ref for repo %s' % (ref, repo))
        if not os.path.exists(repo_dir):
            raise Exception('Repository %s does not exist in the cache' % repo)

        try:
            sha1 = self._rev_parse(repo_dir, ref)
        except BaseException:
            raise Exception('Ref %s is an invalid reference for repo %s' % (ref, repo))

        lines = self._ls_tree(repo_dir, sha1, path).strip()
        lines = lines.splitlines()
        data = {}
        for line in lines:
            elements = line.split()
            basename = elements[3]
            data[basename] = {
                'mode': elements[0],
                'kind': elements[1],
                'sha1': elements[2],
            }
        return data

    def get_bundle_filename(self, repo_url):
        quoted_url = self._quote_url(repo_url, True)
        return os.path.join(self.bundle_cache_dir, '%s.bndl' % quoted_url)
        
    def _quote_url(self, url, always_indirect=False):
        if self.direct_mode and not always_indirect:
            quoted_url = urlparse.urlparse(url)[2]
            while quoted_url.startswith("/"):
                quoted_url = quoted_url[1:]
            return quoted_url
        else:
            valid_chars = string.digits + string.letters + '%_'
            transl = lambda x: x if x in valid_chars else '_'
            return ''.join([transl(x) for x in url])

    def _rev_parse(self, repo_dir, ref):
        return self.app.runcmd(['git', 'rev-parse', '--verify', ref],
                               cwd=repo_dir)[0:40]

    def _cat_file(self, repo_dir, sha1, filename):
        return self.app.runcmd(
                ['git', 'cat-file', 'blob', '%s:%s' % (sha1, filename)],
                cwd=repo_dir)

    def _ls_tree(self, repo_dir, sha1, path):
        return self.app.runcmd(['git', 'ls-tree', sha1, path], cwd=repo_dir)

    def _is_valid_sha1(self, ref):
        valid_chars = 'abcdefABCDEF0123456789'
        return len(ref) == 40 and all([x in valid_chars for x in ref])
