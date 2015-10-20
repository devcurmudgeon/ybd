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
from time import strftime, gmtime
import datetime
import tempfile
import yaml
from bottle import Bottle, request, response, template, static_file
from subprocess import call

from ybd import app

bottle = Bottle()


class KeyedBinaryArtifactServer(object):

    ''' Generic artifact cache server

        Configuration can be found in the associated kbas.conf file.'''

    def __init__(self):
        app.load_configs([
            os.path.join(os.getcwd(), 'kbas.conf'),
            os.path.join(os.path.dirname(__file__), 'config', 'kbas.conf')])
        app.config['start-time'] = datetime.datetime.now()

        # for development:
        if app.config.get('mode') == 'development':
            bottle.run(host=app.config['host'], port=app.config['port'],
                       debug=True, reloader=True)
        else:
            bottle.run(host=app.config['host'], port=app.config['port'])

    @bottle.get('/static/<filename>')
    def send_static(filename):
        current_dir = os.getcwd()
        static_dir = os.path.join(current_dir, 'kbas/public')
        return static_file(filename, root=static_dir)

    @bottle.get('/<name>')
    @bottle.get('/artifacts/<name>')
    def list(name=""):
        current_dir = os.getcwd()
        os.chdir(app.config['artifact-dir'])
        names = glob.glob('*' + name + '*')
        content = [[strftime('%y-%m-%d', gmtime(os.path.getctime(x))), x]
                   for x in names]
        os.chdir(current_dir)
        return template('kbas',
                        title='Available Artifacts:',
                        content=reversed(sorted(content)),
                        css='/static/style.css')

    @bottle.get('/1.0/artifacts')
    def get_morph_artifact():
        f = request.query.filename
        path = os.path.join(app.config['artifact-dir'], f)
        if os.path.exists(path):
            call(['touch', path])
        return static_file(f, root=app.config['artifact-dir'], download=True)

    @bottle.get('/get/<cache_id>')
    def get_artifact(cache_id):
        f = os.path.join(cache_id, cache_id)
        path = os.path.join(app.config['artifact-dir'], f)
        if os.path.exists(path):
            call(['touch', os.path.dirname(path)])
        return static_file(f, root=app.config['artifact-dir'], download=True)

    @bottle.get('/')
    @bottle.get('/status')
    def status():
        stat = os.statvfs(app.config['artifact-dir'])
        free = stat.f_frsize * stat.f_bavail / 1000000000
        artifacts = len(os.listdir(app.config['artifact-dir']))
        started = app.config['start-time'].strftime('%y-%m-%d %H:%M:%S')
        content = [['Started:', started]]
        content += [['Space:', str(free) + 'GB']]
        content += [['Files:', str(artifacts)]]
        return template('kbas',
                        title='KBAS status',
                        content=content,
                        css='/static/style.css')

    @bottle.post('/upload')
    def post_artifact():
        if app.config['password'] is 'insecure' or \
                request.forms.get('password') != app.config['password']:
            print 'Upload attempt: password fail'
            response.status = 401  # unauthorized
            return
        cache_id = request.forms.get('filename')
        if os.path.isdir(os.path.join(app.config['artifact-dir'], cache_id)):
            response.status = 405  # method not allowed, this artifact exists
            return

        tempfile.tempdir = app.config['artifact-dir']
        tmpdir = tempfile.mkdtemp()
        try:
            upload = request.files.get('file')
            upload.save(os.path.join(tmpdir, cache_id))
            os.rename(tmpdir, os.path.join(app.config['artifact-dir'], cache_id))
            response.status = 201  # success!
            return
        except:
            # this was a race, remove the tmpdir
            shutil.rmtree(tmpdir)
            response.status = 999  # method not allowed, this artifact exists

        return


KeyedBinaryArtifactServer().__init__()
