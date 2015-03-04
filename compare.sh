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

cp /src/cache/artifacts/*$1*build-log /src/logs/morph-reference/
sed -i 's|src/tmp/staging/[^/]*|STAGING|g' /src/logs/morph-reference/*

cp /src/cache/ybd-artifacts/$1*build-log /src/logs/ybd
sed -i 's|src/staging/[^/]*/[^/]*|STAGING|g' /src/logs/ybd/$1*
diff /src/logs/morph-reference/*.$1* /src/logs/ybd/$1* | less

echo 'morph' ; tar -tf /src/cache/artifacts/*$1-misc | wc -l
echo 'ybd  ' ; tar -tf /src/cache/ybd-artifacts/$1@*tar.gz | wc -l

tar -tf /src/cache/ybd-artifacts/$1@*tar.gz | cut -c3- | sort > /src/ybd/ybd.output
tar -tf /src/cache/artifacts/*$1-misc | sort > /src/ybd/morph.output

diff /src/ybd/ybd.output /src/ybd/morph.output