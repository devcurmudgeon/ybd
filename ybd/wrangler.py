# Copyright (C) 2015  Codethink Limited
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

import yaml
import os
import app
import cache
from subprocess import check_output
import hashlib
import shutil
from fs.osfs import OSFS

def detect_format(source):
    fs = OSFS(source)
    if fs.walkfiles('/', '*.morph'):
        return 'baserock-morphologies'
    if fs.walkfiles('/', '*.cida'):
        return 'cida-definitions'
    return None


def wrangle_morphs(source, output):
    # rename morph: labels => path:
    # rename strata: and chunks: labels => contents:
    # drop all lines containing empty build-depends
    # rename all .morph files to .cida files
    shutil.copytree(source, output)


def wrangle_cidas(source, output):
    shutil.copytree(source, output)


def wrangle_recipes(source, output):
    app.exit('WRANGLER', 'ERROR: bitbake recipes in', source)


def wrangle(source, output):
    format = detect_format(source)
    if format is not None and output != '/' and os.path.isdir(output):
        shutil.rmtree(output)
    if format == 'baserock-morphologies':
        app.log('WRANGLER', 'baserock morphs found in', source)
        wrangle_morphs(source, output)
    elif format == 'cida-definitions':
        app.log('WRANGLER', 'cida files found in', source)
        wrangle_cida(source, output)
    else:
        app.exit('WRANGLER', 'ERROR: no definitions|recipes found in', source)
