#!/usr/bin/env python
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

import logging
import os
import glob
import shutil
import time
import tempfile
import yaml
from bottle import Bottle, request, response, template, static_file

config = {}
app = Bottle()


class KeyedBinaryArtifactServer(object):

    ''' Generic artifact cache server

        Configuration can be found in the associated kbas.conf file.'''

    def __init__(self):
        conf = './kbas.conf'
        if not os.path.exists(conf):
            conf = os.path.join(os.path.dirname(__file__), 'kbas.conf')
        with open(conf) as f:
            text = f.read()
        for key, value in yaml.safe_load(text).items():
            config[key] = value
        # for development:
        if config['mode'] == 'development':
            app.run(host=config['host'], port=config['port'],
                    debug=True, reloader=True)
        else:
            app.run(host=config['host'], port=config['port'])

    @app.get('/<name>')
    @app.get('/artifacts/<name>')
    def list(name=""):
       current_dir = os.getcwd()
       os.chdir(config['artifact-dir'])
       names = glob.glob('*' + name + '*')
       content = [[x, time.ctime(os.path.getmtime(x))] for x in names]
       os.chdir(current_dir)
       return template('kbas', rows=sorted(content))

    @app.get('/get/<cache_id>')
    def get_artifact(cache_id):
        path = os.path.join(cache_id, cache_id)
        return static_file(path, root=config['artifact-dir'], download=True)

    @app.post('/upload')
    def post_artifact():
        if request.forms.get('password') != config['password']:
            print 'Upload attempt: password fail'
            response.status = 401 # unauthorized
            return
        cache_id = request.forms.get('filename')
        if os.path.isdir(os.path.join(config['artifact-dir'], cache_id)):
            response.status = 405 # method not allowed, this artifact exists
            return

        tempfile.tempdir = config['artifact-dir']
        tmpdir = tempfile.mkdtemp()
        try:
            upload = request.files.get('file')
            upload.save(os.path.join(tmpdir, cache_id))
            os.rename(tmpdir, os.path.join(config['artifact-dir'], cache_id))
            response.status = 201 # success!
            return
        except:
            # this was a race, remove the tmpdir
            shutil.rmtree(tmpdir)
            response.status = 999 # method not allowed, this artifact exists

        return

if __name__ == '__main__':
    KeyedBinaryArtifactServer().__init__()
