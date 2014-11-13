#!/usr/bin/env python3
#
# Copyright (C) 2012-2014  Codethink Limited
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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# =*= License: GPL-2 =*=

import os


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
        self.pre_configure_commands = []
        self.configure_commands = []
        self.post_configure_commands = []
        self.pre_build_commands = []
        self.build_commands = []
        self.post_build_commands = []
        self.pre_test_commands = []
        self.test_commands = []
        self.post_test_commands = []
        self.pre_install_commands = []
        self.install_commands = []
        self.post_install_commands = []

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

    def used_by_project(self, file_list):
        return False


class DummyBuildSystem(BuildSystem):

    '''A dummy build system, useful for debugging definitions.'''

    name = 'dummy'

    def __init__(self):
        BuildSystem.__init__(self)
        self.configure_commands = ['echo dummy configure']
        self.build_commands = ['echo dummy build']
        self.test_commands = ['echo dummy test']
        self.install_commands = ['echo dummy install']

    def used_by_project(self, file_list):
        return False


class AutotoolsBuildSystem(BuildSystem):

    '''The automake/autoconf/libtool holy trinity.'''

    name = 'autotools'

    def __init__(self):
        BuildSystem.__init__(self)
        self.configure_commands = [
            'export NOCONFIGURE=1; ' +
            'if [ -e autogen ]; then ./autogen; ' +
            'elif [ -e autogen.sh ]; then ./autogen.sh; ' +
            'elif [ ! -e ./configure ]; then autoreconf -ivf; fi',
            './configure --prefix="$PREFIX"',
        ]
        self.build_commands = [
            'make',
        ]
        self.test_commands = [
        ]
        self.install_commands = [
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
        self.configure_commands = [
        ]
        self.build_commands = [
            'python setup.py build',
        ]
        self.test_commands = [
        ]
        self.install_commands = [
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
        self.configure_commands = [
            'perl Makefile.PL INSTALLDIRS=perl '
            'INSTALLARCHLIB="$PREFIX/lib/perl" '
            'INSTALLPRIVLIB="$PREFIX/lib/perl" '
            'INSTALLBIN="$PREFIX/bin" '
            'INSTALLSCRIPT="$PREFIX/bin" '
            'INSTALLMAN1DIR="$PREFIX/share/man/man1" '
            'INSTALLMAN3DIR="$PREFIX/share/man/man3"',
        ]
        self.build_commands = [
            'make',
        ]
        self.test_commands = [
        ]
        self.install_commands = [
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
        self.configure_commands = [
            'cmake -DCMAKE_INSTALL_PREFIX=/usr'
        ]
        self.build_commands = [
            'make',
        ]
        self.test_commands = [
        ]
        self.install_commands = [
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
        self.configure_commands = [
            'qmake -makefile '
        ]
        self.build_commands = [
            'make',
        ]
        self.test_commands = [
        ]
        self.install_commands = [
            'make INSTALL_ROOT="$DESTDIR" install',
        ]

    def used_by_project(self, file_list):
        indicator = '.pro'

        for x in file_list:
            if x.endswith(indicator):
                return True

        return False

build_systems = [
    ManualBuildSystem(),
    AutotoolsBuildSystem(),
    PythonDistutilsBuildSystem(),
    CPANBuildSystem(),
    CMakeBuildSystem(),
    QMakeBuildSystem(),
    DummyBuildSystem(),
]


def detect_build_system(file_list):
    '''Automatically detect the build system, if possible.

    If the build system cannot be detected automatically, return None.
    For ``exists`` see the ``BuildSystem.exists`` method.

    '''
    for build_system in build_systems:
        if build_system.used_by_project(file_list):
            return build_system
    return None


def lookup_build_system(name):
    '''Return build system that corresponds to the name.

    If the name does not match any build system, raise ``KeyError``.

    '''

    for build_system in build_systems:
        if build_system.name == name:
            return build_system
    raise KeyError('Unknown build system: %s' % name)
