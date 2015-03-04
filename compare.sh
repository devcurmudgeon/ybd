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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# =*= License: GPL-2 =*=

set -e

usage() {
    echo "Usage: compare.sh <artifact>"
    echo
    echo "This compares morph output with ybd output for a given artifact"
}


if [ -z "$1" ]; then
    usage
    exit 1
fi

cp /src/cache/artifacts/*$1-build-log ./$1.morph-build-log
sed -i 's|src/tmp/staging/[^/]*|STAGING|g' ./$1.morph-build-log

cp /src/cache/ybd-artifacts/$1@*.build-log ./$1.ybd-build-log
sed -i 's|src/staging/[^/]*/[^/]*|STAGING|g' ./$1.ybd-build-log
diff ./$1.morph-build-log ./$1.ybd-build-log | less

echo 'morph' ; tar -tf /src/cache/artifacts/*$1-misc | wc -l
echo 'ybd  ' ; tar -tf /src/cache/ybd-artifacts/$1@*tar.gz | wc -l

tar -tf /src/cache/ybd-artifacts/$1@*tar.gz | cut -c3- | sort > ./ybd.output
tar -tf /src/cache/artifacts/*$1-misc | sort > ./morph.output

diff ./ybd.output ./morph.output
