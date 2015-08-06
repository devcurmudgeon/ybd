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


'''Defaults to be used for older Baserock Definitions.

Definitions version 7 adds a file named DEFAULTS which sets the default
build commands and default split rules for the set of definitions in that
repo.

These definitions shall be used if no DEFAULTS file is present.

'''

import app
import yaml
import buildsystem

_OLD_DEFAULTS = '''# Baserock definitions defaults
build-systems:
  manual:
    # The special, default 'no-op' build system.
    configure-commands: []
    build-commands: []
    install-commands: []
    strip-commands: []

  autotools:
    # GNU Autoconf and GNU Automake, or anything which follow the same pattern.
    configure-commands:
    - |
      export NOCONFIGURE=1;
      if [ -e autogen ]; then ./autogen;
      elif [ -e autogen.sh ]; then ./autogen.sh;
      elif [ ! -e ./configure ]; then autoreconf -ivf;
      fi
      ./configure --prefix="$PREFIX"
    build-commands:
    - make
    install-commands:
    - make DESTDIR="$DESTDIR" install
    strip-commands:
      - &autotools-strip-commands |
        find "$DESTDIR" -type f
          '(' -perm -111 -o -name '*.so*' -o -name '*.cmxs' -o -name '*.node' ')'
          -exec sh -ec
          read -n4 hdr <"$1"   # check for elf header
          if [ "$hdr" != "$(printf \x7ELF)" ]; then
            exit 0
          fi
          debugfile="$DESTDIR$PREFIX/lib/debug/$(basename "$1")"
          mkdir -p "$(dirname "$debugfile")"
          objcopy --only-keep-debug "$1" "$debugfile"
          chmod 644 "$debugfile"
          strip --remove-section=.comment --remove-section=.note --strip-unneeded "$1"
          objcopy --add-gnu-debuglink "$debugfile" "$1"' - {} ';'

  python-distutils:
    # The Python distutils build systems.
    configure-commands: []
    build-commands:
    - python setup.py build
    install-commands:
    - python setup.py install
    strip-commands:
      - *autotools-strip-commands

  cpan:
    # The Perl ExtUtil::MakeMaker build system.
    configure-commands:
      # This is subject to change, see: https://gerrit.baserock.org/#/c/986/
      - |
        perl Makefile.PL INSTALLDIRS=perl
            INSTALLARCHLIB="$PREFIX/lib/perl"
            INSTALLPRIVLIB="$PREFIX/lib/perl"
            INSTALLBIN="$PREFIX/bin"
            INSTALLSCRIPT="$PREFIX/bin"
            INSTALLMAN1DIR="$PREFIX/share/man/man1"
            INSTALLMAN3DIR="$PREFIX/share/man/man3"
    build-commands:
    - make
    install-commands:
    - make DESTDIR="$DESTDIR" install
    strip-commands:
      - *autotools-strip-commands

  cmake:
    # The CMake build system.
    configure-commands:
    - cmake -DCMAKE_INSTALL_PREFIX="$PREFIX"'
    build-commands:
    - make
    install-commands:
    - make DESTDIR="$DESTDIR" install
    strip-commands:
      - *autotools-strip-commands

  qmake:
    # The Qt build system.
    configure-commands:
    - qmake -makefile
    build-commands:
    - make
    install-commands:
    - make INSTALL_ROOT="$DESTDIR" install
    strip-commands:
      - *autotools-strip-commands

split-rules:
  chunk:
    - artifact: -bins
      include:
        - (usr/)?s?bin/.*
    - artifact: -libs
      include:
        - (usr/)?lib(32|64)?/lib[^/]*\.so(\.\d+)*
        - (usr/)libexec/.*
    - artifact: -devel
      include:
        - (usr/)?include/.*
        - (usr/)?lib(32|64)?/lib.*\.a
        - (usr/)?lib(32|64)?/lib.*\.la
        - (usr/)?(lib(32|64)?|share)/pkgconfig/.*\.pc
    - artifact: -doc
      include:
        - (usr/)?share/doc/.*
        - (usr/)?share/man/.*
        - (usr/)?share/info/.*
    - artifact: -locale
      include:
        - (usr/)?share/locale/.*
        - (usr/)?share/i18n/.*
        - (usr/)?share/zoneinfo/.*
    - artifact: -misc
      include:
        - .*

  stratum:
    - artifact: -devel
      include:
        - .*-devel
        - .*-debug
        - .*-doc
    - artifact: -runtime
      include:
        - .*-bins
        - .*-libs
        - .*-locale
        - .*-misc
        - .*
'''


class Defaults(object):

    def __init__(self):
        self._build_systems = {}
        self._split_rules = {}
        data = self._load_defaults()

        build_system_data = data.get('build-systems', {})

        for name, commands in build_system_data.items():
            build_system = buildsystem.BuildSystem()
            build_system.from_dict(name, commands)
            self._build_systems[name] = build_system

        self._split_rules = data.get('split-rules', {})

    def _load(self, path, ignore_errors=True):
        contents = None
        try:
            with open(path) as f:
                contents = yaml.safe_load(f)
        except:
            if ignore_errors:
                app.log('DEFAULTS', 'WARNING: problem loading', path)
                return None
            else:
                raise
        contents['path'] = path[2:]
        return contents

    def _load_defaults(self, defaults_filename='./DEFAULTS'):
        '''Get defaults, either from a DEFAULTS file, or built-in defaults.

        Returns a dict of the defaults tree.
        '''

        data = self._load(defaults_filename, ignore_errors=True)
        if data is None:
            data = yaml.safe_load(_OLD_DEFAULTS)

        return data

    def get_chunk_split_rules(self):
        return self._split_rules.get('chunk', {})

    def get_stratum_split_rules(self):
        return self._split_rules.get('stratum', {})

    def lookup_build_system(self, name, default=None):
        '''Return build system that corresponds to the name.

        If the name does not match any build system, raise ``KeyError``.
        '''

        if name in self._build_systems:
            return self._build_systems[name]
        elif default:
            return default
        else:
            raise KeyError("Undefined build-system %s" % name)
