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

import SimpleHTTPServer
import SocketServer
import cgi
import sys
import os


class ServerHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    def do_GET(self):
        SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        e = {'REQUEST_METHOD': 'POST',
             'CONTENT_TYPE': self.headers['Content-Type'], }
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=e)

        fileitem = form['file']
        if fileitem.filename:
            filename = os.path.join(os.getcwd(),
                                    os.path.basename(fileitem.filename))
            open(filename, 'wb').write(fileitem.file.read())
            print 'SERVER File was uploaded successfully %s' % filename
        else:
            print 'SERVER ERROR: Something went wrong with %s' % filename

        SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)


def start():
    server = 'http://192.168.56.101:8000/'
    port = 8000
    Handler = ServerHandler
    os.chdir('/src/cache/remote')
    print 'SERVER: I am Spartacus!'
    try:
        httpd = SocketServer.TCPServer(("", port), Handler)
        if os.fork() == 0:
            httpd.serve_forever()
            sys.exit()
    except:
        print 'SERVER ERROR: Something went wrong starting SocketServer'
        raise SystemExit

start()
