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
from subprocess import check_output
import tempfile
from ybd import app
from ybd.app import chdir
from ybd.config import config
from ybd.morphs import Morphs
from ybd.repos import explore, get_last_tag, get_repo_name
from ybd.repos import mirror, mirror_has_ref
from ybd.utils import log


def do_release_note(release_note):
    tempfile.tempdir = config['tmp']
    tmpdir = tempfile.mkdtemp()

    if 'release-since' in config:
        ref = config['release-since']
    else:
        ref = get_last_tag('.')

    with explore(ref):
        old_defs = Morphs()._data

    for path in app.defs._data:
        dn = app.defs.get(path)
        if dn.get('cache'):
            log_changes(dn, tmpdir, old_defs, ref)

    count = 0
    with open(release_note, 'w') as f:
        for log_file in os.listdir(tmpdir):
            count += 1
            f.write('====================================================\n\n')
            with open(os.path.join(tmpdir, log_file)) as infile:
                for line in infile:
                    f.write(line)
            f.write('\n\n')
    log('RELEASE NOTE', 'Changes for %s components logged at' % count,
        release_note)


def log_changes(dn, tmpdir, old_defs, ref):
    do_git_log = False
    old_def = old_defs.get(dn['path'])
    log_file = os.path.join(tmpdir, dn['name'])
    with open(log_file, 'w') as f:
        keys = set(dn) - set(['tree', 'cache'])
        for key in keys:
            try:
                old_value = old_def.get(key)
            except:
                old_value = None
            if dn[key] != old_value:
                f.write('[%s] Value changed: %s\n' % (dn['path'], key))
                if type(dn[key]) is str:
                    f.write('%s | %s\n' % (old_value, dn[key]))
                if type(dn[key]) is not str and type(dn[key]) is not float:
                    if old_value:
                        for x in old_value:
                            f.write(repr(x))
                    f.write('\n                vvv\n')
                    if dn[key]:
                        for x in dn[key]:
                            f.write(repr(x))
                f.write('\n\n')

        if dn.get('kind', 'chunk') == 'chunk' and config['release-command']:
            log(dn, 'Logging git change history', tmpdir)
            try:
                gitdir = os.path.join(config['gits'],
                                      get_repo_name(dn['repo']))
                if not os.path.exists(gitdir):
                    mirror(dn['name'], dn['repo'])
                elif not mirror_has_ref(gitdir, ref):
                    update_mirror(dn['name'], dn['repo'], gitdir)
                with chdir(gitdir):
                    text = dn['ref'] + '..'
                    if old_def and old_def.get('ref'):
                        text += old_def['ref']
                    f.write(check_output(config['release-command'] + [text]))
            except:
                log(dn, 'WARNING: Failed to log git changes')
    if os.stat(log_file).st_size == 0:
        os.remove(log_file)
