#!/usr/bin/env bash
# Copyright (C) 2016  Codethink Limited
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

#
# This is a bash script which attempts to install ybd's dependencies.
# It's mainly intended for ci and automated test setups...
#

# echo what we're doing
set -x

SUDO=""
if [ "$(id -u)" -ne 0 ];
  then SUDO="sudo"
fi

installed=false
# install dependencies for debian, ubuntu
command -v apt-get >/dev/null 2>&1
if [ $? -eq 0 ]; then
    $SUDO apt-get -qq update
    $SUDO apt-get -qq remove python-pip
    $SUDO apt-get -qq install build-essential gawk git m4 wget python python-dev git
    if [ $? -ne 0 ]; then
        echo "Install failed"
        exit 1
    fi
    installed=true
fi

# install for fedora
command -v dnf >/dev/null 2>&1
if [ $? -eq 0 ] && [ $installed = false ]; then
    $SUDO dnf remove -y python-pip
    $SUDO dnf install -y which make automake gcc gcc-c++ gawk git m4 wget python python-devel git redhat-rpm-config
    if [ $? -ne 0 ]; then
        echo "Install failed"
        exit 1
    fi
    installed=true
fi

# install for aws
command -v yum >/dev/null 2>&1
if [ $? -eq 0 ] && [ $installed = false ]; then
    $SUDO yum remove -y python-pip
    $SUDO yum install -y which make automake gcc gcc-c++ gawk git m4 wget python python-devel git
    if [ $? -ne 0 ]; then
        echo "Install failed"
        exit 1
    fi
    installed=true
fi

# install for Arch
command -v pacman >/dev/null 2>&1
if [ $? -eq 0 ] && [ $installed = false ]; then
    $SUDO pacman -S --noconfirm which make automake gcc gawk git m4 wget python2 git
    if [ $? -ne 0 ]; then
        echo "Install failed"
        exit 1
    fi
    installed=true
fi

if [ $installed = false ]; then
    echo "No way to install dependencies: [apt|dnf|yum|pacman] not found"
    exit 1
fi

pip --version 2>&1 > /dev/null
if [ $? -ne 0 ]; then
    wget https://bootstrap.pypa.io/get-pip.py
    chmod +x get-pip.py
    $SUDO ./get-pip.py
    $SUDO rm get-pip.py
fi

$SUDO pip install -U pip

$SUDO pip install -U -r requirements.freeze.txt
