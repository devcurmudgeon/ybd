#!/usr/bin/env python
# Copyright (C) 2015-2016  Codethink Limited
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
import glob
import shutil
from time import strftime, gmtime
from datetime import datetime
import tempfile
from bottle import Bottle, request, response, template, static_file
from subprocess import call

from ybd import app, cache

bottle = Bottle()


class KeyedBinaryArtifactServer(object):

    ''' Generic artifact cache server

        Configuration can be found in the associated kbas.conf file.'''

    def __init__(self):
        app.load_configs([
            os.path.join(os.getcwd(), 'kbas.conf'),
            os.path.join(os.path.dirname(__file__), 'config', 'kbas.conf')])
        app.config['start-time'] = datetime.now()
        app.config['last-upload'] = datetime.now()

        try:
            import cherrypy
            server = 'cherrypy'
        except:
            server = 'wsgiref'

        # for development:
        if app.config.get('mode') == 'development':
            bottle.run(server=server, host=app.config['host'],
                       port=app.config['port'], debug=True, reloader=True)
        else:
            bottle.run(server=server, host=app.config['host'],
                       port=app.config['port'], reloader=True)

    @bottle.get('/static/<filename>')
    def send_static(filename):
        current_dir = os.getcwd()
        static_dir = os.path.join(current_dir, 'kbas/public')
        return static_file(filename, root=static_dir)

    @bottle.get('/<name>')
    @bottle.get('/artifacts/<name>')
    def list(name=""):
        names = glob.glob(os.path.join(app.config['artifact-dir'],
                          '*' + name + '*'))
        try:
            content = [[strftime('%y-%m-%d', gmtime(os.stat(x).st_atime)),
                       cache.check(os.path.basename(x)),
                       os.path.basename(x)] for x in names]
        except:
            content = [['--------',
                       cache.check(os.path.basename(x)),
                       os.path.basename(x)] for x in names]

        return template('kbas',
                        title='Available Artifacts:',
                        content=reversed(sorted(content)),
                        css='static/style.css')

    @bottle.get('/1.0/artifacts')
    def get_morph_artifact():
        f = request.query.filename
        return static_file(f, root=app.config['artifact-dir'], download=True)

    @bottle.get('/get/<cache_id>')
    def get_artifact(cache_id):
        f = os.path.join(cache_id, cache_id)
        return static_file(f, root=app.config['artifact-dir'], download=True)

    @bottle.get('/')
    @bottle.get('/status')
    def status():
        stat = os.statvfs(app.config['artifact-dir'])
        free = stat.f_frsize * stat.f_bavail / 1000000000
        artifacts = len(os.listdir(app.config['artifact-dir']))
        started = app.config['start-time'].strftime('%y-%m-%d %H:%M:%S')
        last_upload = app.config['last-upload'].strftime('%y-%m-%d %H:%M:%S')
        content = [['Started:', started]]
        content += [['Last upload:', last_upload]]
        if app.config.get('last-reject'):
            content += [['Last reject:', app.config['last-reject']]]
        content += [['Space:', str(free) + 'GB']]
        content += [['Artifacts:', str(artifacts)]]
        return template('kbas',
                        title='KBAS status',
                        content=content,
                        css='static/style.css')

    @bottle.post('/upload')
    def post_artifact():
        if app.config['password'] is 'insecure' or \
                request.forms.get('password') != app.config['password']:
            print 'Upload attempt: password fail'
            app.config['last-reject'] = \
                datetime.now().strftime('%y-%m-%d %H:%M:%S')
            response.status = 401  # unauthorized
            return

        cache_id = request.forms.get('filename')
        if re.match('^[a-zA-Z0-9\.\-\_]*$', cache_id) is None:
            response.status = 400  # bad request, cache_id contains bad things
            return

        if os.path.isdir(os.path.join(app.config['artifact-dir'], cache_id)):
            if cache.check(cache_id) == request.forms.get('checksum', 'XYZ'):
                response.status = 777  # this is the same binary we have
                return
            response.status = 405  # not allowed, this artifact exists
            return

        tempfile.tempdir = app.config['artifact-dir']
        tmpdir = tempfile.mkdtemp()
        try:
            upload = request.files.get('file')
            artifact = os.path.join(tmpdir, cache_id)

            try:
                upload.save(artifact)
            except:
                # upload.save is only available in recent versions of bottle
                # troves (for example) have an older version... hence:
                with open(artifact, "w") as f:
                    f.write(upload.value)

            if call(['tar', 'tf', artifact]):
                app.log('UPLOAD', 'ERROR: not a valid tarfile:', artifact)
                raise
            checksum = cache.md5(artifact)
            with open(artifact + '.md5', "a") as f:
                f.write(checksum)
            shutil.move(tmpdir, os.path.join(app.config['artifact-dir'],
                                             cache_id))
            response.status = 201  # success!
            app.config['last-upload'] = datetime.now()
            return
        except:
            # something went wrong, clean up
            import traceback
            traceback.print_exc()
            try:
                shutil.rmtree(tmpdir)
            except:
                pass
            response.status = 500

        return


KeyedBinaryArtifactServer().__init__()
