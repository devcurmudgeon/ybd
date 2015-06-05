#!/usr/bin/env python3
#
# Copyright (C) 2012-2015  Codethink Limited
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


build_steps = ['pre-configure-commands',
               'configure-commands',
               'post-configure-commands',
               'pre-build-commands',
               'build-commands',
               'post-build-commands',
               'pre-test-commands',
               'test-commands',
               'post-test-commands',
               'pre-install-commands',
               'install-commands',
               'post-install-commands',
               'pre-strip-commands',
               'strip-commands',
               'post-strip-commands']


_STRIP_COMMAND = r'''find "$DESTDIR" -type f \
  '(' -perm -111 -o -name '*.so*' -o -name '*.cmxs' -o -name '*.node' ')' \
  -exec sh -ec \
  'read -n4 hdr <"$1" # check for elf header
   if [ "$hdr" != "$(printf \\x7fELF)" ]; then
       exit 0
   fi
   debugfile="$DESTDIR$PREFIX/lib/debug/$(basename "$1")"
   mkdir -p "$(dirname "$debugfile")"
   objcopy --only-keep-debug "$1" "$debugfile"
   chmod 644 "$debugfile"
   strip --remove-section=.comment --remove-section=.note --strip-unneeded "$1"
   objcopy --add-gnu-debuglink "$debugfile" "$1"' - {} ';'
'''


class BuildSystem(object):

    '''An abstraction of an upstream build system.

    Some build systems are well known: autotools, for example.
    Others are purely manual: there's a set of commands to run that
    are specific for that project, and (almost) no other project uses them.
    The Linux kernel would be an example of that.

    This class provides an abstraction for these, including a method
    to autodetect well known build systems.

    '''

    def __init__(self):
        self.commands = {}
        self.commands['strip-commands'] = [_STRIP_COMMAND]

    def __getitem__(self, key):
        key = '_'.join(key.split('-'))
        return getattr(self, key)

    def used_by_project(self, file_list):
        '''Does a project use this build system?

        ``exists`` is a function that returns a boolean telling if a
        filename, relative to the project source directory, exists or not.

        '''
        raise NotImplementedError()  # pragma: no cover


class ManualBuildSystem(BuildSystem):

    '''A manual build system where the definition must specify all commands.'''

    name = 'manual'

    def __init__(self):
        BuildSystem.__init__(self)
        self.commands['configure-commands'] = []
        self.commands['build-commands'] = []
        self.commands['install-commands'] = []

    def used_by_project(self, file_list):
        return False


class AutotoolsBuildSystem(BuildSystem):

    '''The automake/autoconf/libtool holy trinity.'''

    name = 'autotools'

    def __init__(self):
        BuildSystem.__init__(self)
        self.commands['configure-commands'] = [
            'export NOCONFIGURE=1; ' +
            'if [ -e autogen ]; then ./autogen; ' +
            'elif [ -e autogen.sh ]; then ./autogen.sh; ' +
            'elif [ ! -e ./configure ]; then autoreconf -ivf; fi',
            './configure --prefix="$PREFIX"',
        ]
        self.commands['build-commands'] = [
            'make',
        ]
        self.commands['test-commands'] = [
        ]
        self.commands['install-commands'] = [
            'make DESTDIR="$DESTDIR" install',
        ]

    def used_by_project(self, file_list):
        indicators = [
            'autogen',
            'autogen.sh',
            'configure',
            'configure.ac',
            'configure.in',
            'configure.in.in',
        ]

        return any(x in file_list for x in indicators)


class PythonDistutilsBuildSystem(BuildSystem):

    '''The Python distutils build systems.'''

    name = 'python-distutils'

    def __init__(self):
        BuildSystem.__init__(self)
        self.commands['configure-commands'] = [
        ]
        self.commands['build-commands'] = [
            'python setup.py build',
        ]
        self.commands['test-commands'] = [
        ]
        self.commands['install-commands'] = [
            'python setup.py install --prefix "$PREFIX" --root "$DESTDIR"',
        ]

    def used_by_project(self, file_list):
        indicators = [
            'setup.py',
        ]

        return any(x in file_list for x in indicators)


class CPANBuildSystem(BuildSystem):

    '''The Perl cpan build system.'''

    name = 'cpan'

    def __init__(self):
        BuildSystem.__init__(self)
        self.commands['configure-commands'] = [
            'perl Makefile.PL INSTALLDIRS=perl '
            'INSTALLARCHLIB="$PREFIX/lib/perl" '
            'INSTALLPRIVLIB="$PREFIX/lib/perl" '
            'INSTALLBIN="$PREFIX/bin" '
            'INSTALLSCRIPT="$PREFIX/bin" '
            'INSTALLMAN1DIR="$PREFIX/share/man/man1" '
            'INSTALLMAN3DIR="$PREFIX/share/man/man3"',
        ]
        self.commands['build-commands'] = [
            'make',
        ]
        self.commands['test-commands'] = [
        ]
        self.commands['install-commands'] = [
            'make DESTDIR="$DESTDIR" install',
        ]

    def used_by_project(self, file_list):
        indicators = [
            'Makefile.PL',
        ]

        return any(x in file_list for x in indicators)


class CMakeBuildSystem(BuildSystem):

    '''The cmake build system.'''

    name = 'cmake'

    def __init__(self):
        BuildSystem.__init__(self)
        self.commands['configure-commands'] = [
            'cmake -DCMAKE_INSTALL_PREFIX=/usr'
        ]
        self.commands['build-commands'] = [
            'make',
        ]
        self.commands['test-commands'] = [
        ]
        self.commands['install-commands'] = [
            'make DESTDIR="$DESTDIR" install',
        ]

    def used_by_project(self, file_list):
        indicators = [
            'CMakeLists.txt',
        ]

        return any(x in file_list for x in indicators)


class QMakeBuildSystem(BuildSystem):

    '''The Qt build system.'''

    name = 'qmake'

    def __init__(self):
        BuildSystem.__init__(self)
        self.commands['configure-commands'] = [
            'qmake -makefile '
        ]
        self.commands['build-commands'] = [
            'make',
        ]
        self.commands['test-commands'] = [
        ]
        self.commands['install-commands'] = [
            'make INSTALL_ROOT="$DESTDIR" install',
        ]

    def used_by_project(self, file_list):
        indicator = '.pro'

        for x in file_list:
            if x.endswith(indicator):
                return True

        return False

build_systems = [
    AutotoolsBuildSystem(),
    PythonDistutilsBuildSystem(),
    CPANBuildSystem(),
    CMakeBuildSystem(),
    QMakeBuildSystem()
]


def detect_build_system(file_list):

    '''Automatically detect the build system, if possible.'''

    for build_system in build_systems:
        if build_system.used_by_project(file_list):
            return build_system
    return ManualBuildSystem()
