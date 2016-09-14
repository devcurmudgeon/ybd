GitLab: [![build status](https://gitlab.com/baserock/ybd/badges/master/build.svg)](https://gitlab.com/baserock/ybd/commits/master)

Github: [![Build Status](https://travis-ci.org/devcurmudgeon/ybd.svg?branch=master)](https://travis-ci.org/devcurmudgeon/ybd)

# ybd

ybd is a tool for building integrated software stacks. it does four things:

- parse yaml files which describe integrated collections of software components
- gather source code (from git repos) for a user-specified target collection
- build the collection
- optionally deploy the collection (if the yaml files describe where/how to deploy)

currently ybd understands the semantics of yaml
[definitions](http://git.baserock.org/cgi-bin/cgit.cgi/baserock/baserock/definitions.git/tree/)
from the [Baserock](http://wiki.baserock.org) project.

the total codebase for ybd is only ~ 2200 lines of Python. even so ybd can
reliably build all systems in Baserock's definitions.git, i.e. all of the
FOSS components required for Linux appliances up to and including:

- minimal Linux systems
- self-hosting development systems
- GENIVI Baseline and GENIVI Demo Platform systems for x86 and ARMv7
- OpenStack appliances
- OpenWRT appliances

there are Concourse pipelines using ybd to integrate various examples at
concourse.baserock.org...

[<img src="http://i.imgur.com/N193G9C.png" height="400" width="600">](http://concourse.baserock.org)

ybd is a simple start-point for building, deploying, learning and
experimenting with definitions, algorithms and functionality on Baserock
projects. with a little work it can be used to build other software stacks too.

ybd is under development. things will change :) If you're trying ybd for the
first time please start with the latest tag, not master.

ybd is designed for Linux, but can be used on other environments (eg
MacOS) using Vagrant and VirtualBox.

## quick start

on Fedora, Ubuntu, Debian (as root... hoping to fix this for non-root soon):

```
    git clone git://gitlab.com/baserock/ybd && cd ybd
    # checkout latest tag
    git checkout `git describe --tags $(git rev-list --tags --max-count=1)`
    sudo sh ./install_dependencies.sh
    cd .. && git clone git://git.baserock.org/baserock/baserock/definitions
    cd definitions
```

or using Vagrant with VirtualBox:

```
    git clone git://gitlab.com/baserock/ybd && cd ybd
    # checkout latest tag
    git checkout `git describe --tags $(git rev-list --tags --max-count=1)`
    vagrant up
    vagrant ssh
    sudo -i
    cd /src/definitions
```

once there you can run (as root)

```
    ../ybd/ybd.py $1 $2
```

where

- $1 is relative path to a chunk, stratum, system or cluster definition file
- $2 specifies the architecture you're building/deploying for.

note that all of the current baserock definitions are for native builds, no
cross-compile. so if you're on a PC/Mac it may be that your only
option for $2 is x86_64

Some examples to try:

```
   # on an x86_64 laptop running linux, to build a build-system...
   ../ybd/ybd.py systems/build-system-x86_64.morph x86_64

   # on the same laptop, to build gcc (and its dependencies)
   ../ybd/ybd.py gcc x86_64

   # on the same laptop, to build the genivi stratum (and its dependencies)
   ../ybd/ybd.py strata/genivi.morph x86_64

   # on a jetson, to build a GENIVI baseline system...
   ../ybd/ybd.py systems/genivi-baseline-system-armv7lhf-jetson.morph armv7lhf

   # on anything, to build (and deploy?) parts of baserock release...
   ../ybd/ybd.py clusters/release.morph x86_64

   # in a baserock devel vm (x86_64), to build and deploy a self-upgrade...
   ../ybd/ybd.py clusters/upgrade-devel.morph x86_64
```

ybd generates a lot of log output to stdout, which hopefully helps
to explain what is happening. if you need a permanent log then try

```
    ../ybd/ybd.py clusters/upgrade-devel.morph x86_64 | tee some-memorable-name.log
```
More information about ybd's dependencies is in docs/dependencies.md


## configuration

ybd is designed to be run from the command line and/or as part of an
automated pipeline. all configuration is taken from conf files and/or
environment variables, in the following order of precedence:

```
    YBD_* environment variables         # if found
    ./ybd.conf                          # if found
    $path/to/ybd.py/ybd.conf            # if found
    $path/to/ybd.py/ybd/config/ybd.conf # default, as provided in the ybd repo
```

this means you can set custom config via env vars, or the definitions
top-level directory, or the ybd top-level directory, without having to modify
the supplied default [ybd.conf](ybd/config/ybd.conf).

NOTE we recommend you create your own ybd.conf file. that way you can git
merge new versions of ybd + definitions, and your custom settings will always
take precedence, with no possibility of a merge conflict.

to set config via environment variables, each must be prefixed with ```YBD_```
and using ```_``` instead of ```-```. ybd will strip the YBD_ prefix and
convert ```_``` to ```-```, for example

```
    export YBD_artifact_version=1     # artifact-version: 1
    export YBD_log_verbose=True       # log-verbose: True
    export YBD_instances=2            # instances: 2
```

ybd does not support unix-style --flags so far. if enough people complain about
that, it can be fixed.

For details about the config options themselves, see
[ybd.conf](ybd/config/ybd.conf).

## interesting features

### run ybd in parallel
ybd can fork several instances of itself to parallelise its work. there is no
intelligence in the scheduling - all of the forks just randomise
their build-order and try to build everything. for building a set of overlapping
systems in parallel on a many core machine this proves to be quite
effective. For example on a 36-core AWS c4.8xlarge machine, 4 racing instances
of ybd can build all of the x86_64 systems in definitions/clusters/ci.morph
much faster than a single instance.

to try it, just set the `instances` config variable, for example

```
    # as an environment variable...
    export YBD_instances=4

    # or in a ybd.conf file...
    instances: 8
```

you should probably think about setting `max-jobs` too, taking into account
your workloads and host machine(s). if `max-jobs` is not set, ybd will default
it to `number-of-cores/instances`.


### kbas cache server
kbas is a basic server which can be used to allow other users to access
pre-built artifacts from previous or current runs of ybd. See kbas/kbas.py for
the code. with minimal configuration it can serve artifacts to instances of
ybd on other machines, and also receive uploaded artifacts.

to launch kbas, just do

```
    cd kbas && ./kbas.py
```

by default ybd is configured to check for artifacts from a kbas server at

```
    http://artifacts1.baserock.org:8000/

config for kbas follows the same approach as ybd, defaulting to config in

    kbas/config/kbas.conf

NOTE: the default password is 'insecure' and the uploading is disabled unless
you change it.

```


### concourse pipelines
[WORK IN PROGRESS] ybd can generate concourse pipelines - see the code at
ybd/concourse.py

to start a local concourse instance:
```
    # in your definitions directory
    vagrant init concourse/lite
    vagrant up
    # generate pipeline, run concourse.py (same arguments as ybd.py)
    python ../ybd/ybd/concourse.py <target> <arch>
    fly -t local login -c http://192.168.100.4:8080
    fly -t local set-pipeline -p <target> -c <target>.yml
```

you can view the local pipelines at http://192.168.100.4:8080

## todo

in no particular order, here's a list of things that may be interesting to try
doing to/with ybd:
- pip install
- deterministic (bit-for-bit) build
- fix deployment: ybd currently can deploy systems, subsystems (test this?) 
  and upgrades, but it's a mess
  - can't select which subsystems to deploy (need to iron out the definitions)
  - alter the deployment parameters (templating, or commandline?)
  - deploy other-architecture stuff
- run without root privileges on non-Linux environments (eg Mac OS - needs a
  different isolation method instead of linux-user-chroot)
- test assumptions by creating definitions for other OS software sets, eg
  Aboriginal Linux and non-Linux systems
- test/fix to work on old versions of definitions, and on morphs.git
  (and separate out the idiosyncrasies, so code is tidy for future changes)

## project guidelines

- contributions are extremely welcome - feedback, ideas, suggestions, bugs,
  documentation will be appreciated just as much as code.
- key criteria for code contributions are
  - 'Code LESS: every line creates a work-chain. Code is a liability, not an 
    asset'
  - think hard before adding dependencies
  - code should be tested and pass pep8

## license

- license is GPLv2 but other licensing can be considered on request
- most of the copyright is currently Codethink but don't let that put you off.
  There's no intent to keep this as a Codethink-only project, nor will there
  be any attempt to get folks to sign a contributor agreement.
  contributors retain their own copyright.

