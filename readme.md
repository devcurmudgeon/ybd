Github: [![Build Status](https://travis-ci.org/devcurmudgeon/ybd.svg?branch=master)](https://travis-ci.org/devcurmudgeon/ybd) Gitlab: [![Build Status](https://gitlab.com/devcurmudgeon/ybd/badges/master/build.svg)](https://gitlab.com/devcurmudgeon/ybd/badges/master/build.svg)

## ybd

ybd is a tool for building integrated software stacks. it does four things:

- parse yaml files which describe integrated collections of software components
- gather source code (from git repos) for a user-specified target collection
- build the collection
- deploy the collection (if the yaml files describe where/how to deploy)

currently ybd understands the semantics of yaml
[definitions](http://git.baserock.org/cgi-bin/cgit.cgi/baserock/baserock/definitions.git/tree/)
from the [Baserock](http://wiki.baserock.org) project.

the total codebase for ybd is only ~ 2100 lines of Python. even so ybd can
repeatably build all systems in Baserock's definitions.git, i.e. all of the
FOSS components required for Linux appliances up to and including, for example

- self-hosting Linux development systems
- GENIVI Baseline and GENIVI Demo Platform systems for x86 and ARMv7
- OpenStack appliances
- OpenWRT appliances

ybd is a simple start-point for building, deploying, learning and
experimenting with definitions, algorithms and functionality on Baserock
projects. with a little work it can be used to build other software stacks too.

ybd is under development. things will change :) If you're trying ybd for the
first time please start with the latest tag, not master.

### dependencies

currently ybd is for Linux only, but can be used on environments (eg MacOS) using Vagrant and VirtualBox. 

ybd requires git, gcc, make, autotools, python, tar, wget. note that the Baserock definitions also require gawk.

so for a Debian-based system:

    apt-get update; apt-get install build-essential gawk git m4

...and a Fedora-based system:

    yum install make automake gcc gcc-c++ kernel-devel git gawk m4

ybd also depends on [pyfilesystem](http://pyfilesystem.org),
[pyyaml](http://pyyaml.org/wiki/PyYAML),
[sandboxlib](https://github.com/CodethinkLabs/sandboxlib),
[requests](https://github.com/kennethreitz/requests),
and optionally [jsonschema](https://github.com/Julian/jsonschema).

to serve artifacts using kbas, it additionally requires
[bottle](https://github.com/bottlepy/bottle) and optionally
[cherrypy](https://github.com/cherrypy/cherrypy.git)

to use the Riemann functionality, it additionally requires
[riemann-client](https://github.com/borntyping/python-riemann-client)

if you trust the Python Package Index (PyPI) and pip is available on your
machine, you can install these dependencies with:

```
    pip install fs pyyaml sandboxlib requests jsonschema bottle cherrypy riemann-client
```

If you need to install pip itself:

```
    wget https://bootstrap.pypa.io/get-pip.py
    python get-pip.py
```


### quick start

```
    git clone git://github.com/devcurmudgeon/ybd && cd ybd
    # checkout latest tag
    git checkout `git describe --tags $(git rev-list --tags --max-count=1)`
    cd .. && git clone git://git.baserock.org/baserock/baserock/definitions
    cd definitions
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

currently ybd generates a lot of log output to stdout, which hopefully helps
to explain what is happening. if you need a permanent log then try

    ../ybd/ybd.py clusters/upgrade-devel.morph x86_64 | tee some-memorable-name.log

### configuration

ybd is designed to be run from the command line and/or as part of an
automated pipeline. all configuration is taken from conf files, in the
following order of precedence:

    
    ./ybd.conf                          # if found
    $path/to/ybd.py/ybd.conf            # if found
    $path/to/ybd.py/ybd/config/ybd.conf # default, as provided in the ybd repo

this means that it's possible to have custom config in either the definitions top-level directory, or the ybd top-level directory, without having to modify
the supplied default ybd.conf file. creating your own ybd.conf file means
you can merge new/latest ybd using git with no possibility of a conflict,
and your custom settings will continue to take precedence.

for various reasons so far ybd does not support unix-style commandline --flags. if enough people complain about this, it can be fixed.

config values you may want to override include:

    aliases: # shortnames for commonly used online git resources
      'baserock:': 'git://git.baserock.org/baserock/'
      'freedesktop:': 'git://anongit.freedesktop.org/'
      'github:': 'git://github.com/'
      'gnome:': 'git://git.gnome.org/'
      'upstream:': 'git://git.baserock.org/delta/'
    artifact-version: 1 # new in 16.06, allows versioning of artifact key
    base-path: ['/usr/bin', '/bin', '/usr/sbin', '/sbin'] # default build path
    defaults: 'config/defaults.conf' # definitions defaults if not found elsewhere
    directories:
      'artifacts': # where ybd saves/finds built artifacts
      'base': ybd # where ybd works by default if directories are not specified
      'ccache_dir': # where ccache results are saved
      'deployment': # working directory for deployments
      'gits': # where local copies of git repos are saved
      'tmp': # where sandboxes and other tmp directories are created
    kbas-url: 'http://foo.bar/' # kbas location to find pre-built artifacts
    kbas-password: 'insecure' # password if you want to push artifacts to kbas
    log-elapsed: True # log elapsed times since start, or actual time
    log-verbose: False # log extra info including all sandbox installation steps
    min-gigabytes: 10 # space required by ybd. artifacts are culled to free this
    mode: ['keys-only', 'no-build', 'normal'] # for testing/debugging ybd
    reproduce: False # if True, build and compare against artifacts on server
    schemas: # files defining schemas for definitions (currently schemas/*)
    schema-validation: False # set to True to warn, 'strict' to exit on error
    tar-url: 'http://git.baserock.org/tarballs'  # trove service for faster clones
    tree-server: 'http://git.baserock.org:8080/1.0/sha1s?' # another trove service
    riemann-server: '127.0.0.1' # address of a riemann server to optionally send events to
    riemann-port: 5555 # associated port of riemann server

### interesting features

#### run ybd in parallel
ybd can fork several instances of itself to parallelise its work. there is no
intelligence in the scheduling at this point - all of the forks just randomise
their build-order and try to build everything. for building a set of overlapping systems in parallel on a many core machine this proves to be quite
effective. For example on a 36-core AWS c4.8xlarge machine, 4 racing instances
of ybd can build all of the x86_64 systems in definitions/clusters/ci.morph
much faster than a single instance.

#### kbas cache server
there's a basic server which can be used to allow other users to access
pre-built artifacts from previous or current runs of ybd. See kbas.py for the
code. with minimal configuration it can serve artifacts to instances of ybd on
other machines, and also receive uploaded artifacts.


### comparison with morph

- morph does lots of things ybd can't do, and has more config options
- ybd has core functionality only - parse definitions, build, cache artifacts
- no branch|checkout|edit|merge (use git and be done)
- no need for workspaces
- no need to be in a Baserock vm or a Baserock chroot - ybd runs on
other Linux operating systems (eg Ubuntu, Fedora, Debian) and maybe even
non-Linux operating systems (eg BSD, MacOS). However it may be have differently and current Baserock definitions are Linux-specific.
- ybd has an order of magnitude less code, so
  - easier to try things, easier to change things, easier to debug things
  - less to break, less to maintain, less to audit
- ybd aims to have less dependencies
- ybd has faster, simpler calculation of cache-keys, and faster resolution of
  build-order
- ybd aims to drop the words morphology, stratum, chunk from the Baserock
  vocabulary
- ybd recognises generic 'definitions'
  - a definition can contain definitions, nested
  - definitions can be stored in one file or many, one directory or many
  - a definition can have contents and build-dependencies
  - contents are just a list of definitions
  - build-dependencies are just a list of definitions too
- ybd can build any level of component (apparently morph can do this too now?)
  - an individual software component - what we've called a chunk until now
  - a logically-coupled set of components - what we've called a stratum
  - a bootable collection of sets of components - what we've called a system
  - a cluster
- some opinionated tweaks to the presentation of logged info, including
  - eg [flex] Upstream version upstream:flex de10f98e (flex-2-5-35 + 34 commits)
  - Elapsed time for each component, and group of components, and overall build
  - log the actual configure/build/install commands being run

### todo

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

### project guidelines

- contributions are extremely welcome - feedback, ideas, suggestions, bugs,
  documentation will be appreciated just as much as code.
- key criteria for code contributions are
  - 'Code LESS: every line creates a work-chain. Code is a liability, not an 
    asset'
  - think hard before adding dependencies
  - code should be tested and pass pep8
- upstream is at github because we need to build loads of stuff from github
  *anyway* and it's the easiest workflow/infrastructure for a small project.
  ybd will *remain* a small project.

### license

- license is GPLv2 but other licensing can be considered on request
- most of the copyright is currently Codethink but don't let that put you off.
  There's no intent to keep this as a Codethink-only project, nor will there
  be any attempt to get folks to sign a contributor agreement.
  contributors retain their own copyright.

