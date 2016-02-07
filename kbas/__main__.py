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

        def check(artifact):
            try:
                artifact = os.path.join(app.config['artifact-dir'], artifact,
                                         artifact)
                checkfile = artifact + '.md5'
                if not os.path.exists(checkfile):
                    checksum = app.md5(artifact)
                    with open(checkfile, "a") as f:
                        f.write(checksum)

                return(open(checkfile).read())
            except:
                return('================================')

        current_dir = os.getcwd()
        os.chdir(app.config['artifact-dir'])
        names = glob.glob('*' + name + '*')
        content = [[strftime('%y-%m-%d', gmtime(os.path.getctime(x))),
                   check(x), x] for x in names]
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
            artifact = os.path.join(tmpdir, cache_id)
            upload.save(artifact)
            unpackdir = artifact + '.unpacked'
            os.makedirs(unpackdir)
            if call(['tar', 'xf', artifact, '--directory', unpackdir]):
                app.log(this, 'ERROR: Problem unpacking', artifact)
                raise
            shutil.rmtree(unpackdir)
            os.rename(tmpdir, os.path.join(app.config['artifact-dir'],
                                           cache_id))
            checksum = app.md5(artifact)
            with open(artifact + '.md5', "a") as f:
                write(f, checksum)
            response.status = 201  # success!
            return
        except:
            # something went wrong, clean up
            shutil.rmtree(tmpdir)
            response.status = 999

        return


KeyedBinaryArtifactServer().__init__()
