# ybd

ybd is a tool for integrating software stacks. it does four things:

- parse yaml files which describe integrated collections of software components
- gather source code (from git repos) for a user-specified target collection
- build the collection
- deploy the collection (if the yaml files describe where/how to deploy)

currently ybd understands the semantics of yaml
[definitions](http://git.baserock.org/cgi-bin/cgit.cgi/baserock/baserock/definitions.git/tree/)
from the [Baserock](http://wiki.baserock.org) project. ybd provides some of the
functionality of Baserock morph, without most of the complexity that morph has
accrued since development started in 2011.

ybd can be a simple start-point for building, deploying, learning and
experimenting with definitions, algorithms and functionality on Baserock
projects. with a little work it can be used to build other software stacks too.

the ybd codebase is currently only ~ 2000 lines of Python in 12 source files.
even so ybd can reproducibly build all systems in Baserock's definitions.git,
i.e. all of the FOSS components required for Linux appliances up to and
including, for example

- self-hosting Linux development systems
- GENIVI baseline systems
- OpenStack appliances
- OpenWRT appliances

it can also deploy some systems in some ways.

ybd is under development. things will change :) If you're trying ybd for the
first time please start with the latest tag, not master.

### dependencies

currently ybd is for Linux only, and requires git, gcc, make, autotools,
python, tar, wget. note that the Baserock definitions also
require gawk.

so for a Debian-based system:

    apt-get update; apt-get install build-essential gawk git m4

...and a Fedora-based system:

    yum install make automake gcc gcc-c++ kernel-devel git gawk m4

ybd also depends on [pyyaml](http://pyyaml.org/wiki/PyYAML),
[sandboxlib](https://github.com/CodethinkLabs/sandboxlib),
and optionally [jsonschema](https://github.com/Julian/jsonschema) and
[bottle](https://github.com/bottlepy/bottle)

if you trust the Python Package Index (PyPI) and pip is available on your
machine, you can install them with:

```
    pip install pyyaml sandboxlib jsonschema bottle
```

if you need to install pip itself:

```
    wget https://bootstrap.pypa.io/get-pip.py
    python get-pip.py
```


### quick start

```
    git clone git://github.com/devcurmudgeon/ybd
    git clone git://git.baserock.org/baserock/baserock/definitions
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
cross-compile. so if you're on a typical laptop it may be that your only
option for $2 is `x86_64`

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


### experimental features

#### run ybd in parallel
ybd can fork several instances of itself to parallelise its work. there is no
intelligence in the scheduling at this point - all of the forks just randomise
their build-order and try to build everything. the result is lots of races, but
for building a set of overlapping systems in parallel on a many core machine it
proves to be quite effective if not 100% efficient. For example on a 40-core
AWS m4.10xlarge machine, 5 racing instances of ybd take only 90 minutes to
build the x86_64 systems in definitions/clusters/ci.morph

#### cache server
there's a basic server which can be used to allow other users to access
pre-built artifacts from previous or current runs of ybd. See kbas.py for the
code. with minimal configuration it can serve artifacts to instances of ybd on
other machines, and also receive uploaded artifacts too.


### comparison with morph

- morph does lots of things ybd can't do, and has lots of config options
- ybd has core functionality only - parse definitions, build, cache artifacts
- no branch|checkout|edit|merge (use git and be done)
- no need for workspaces
- no need to be in a Baserock vm or a Baserock chroot - ybd runs on
other Linux operating systems (eg Ubuntu, Fedora, Debian) and maybe even
non-Linux operating systems (eg BSD, MacOS). However it may be have differently
and current Baserock definitions are Linux-specific.
- ybd has an order of magnitude less code, so
  - easier to try things, easier to change things, easier to debug things
  - less to break, less to maintain, less to audit
- ybd aims to have less dependencies
- ybd has faster, simpler calculation of cache-keys, and faster resolution of
  build-order
- ybd can drop the words morphology, stratum, chunk from the Baserock vocabulary
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
- command line syntax and args
- add some or all of ybd to definitions, as reference code to parse and build
  definitions.

### and if possible

- establish a common cache algorithm/name/standard with Baserock upstream
- establish roadmap for improvements to definitions format, based on lessons
  from ybd, morph, Ansible, Cloud Foundry and other projects defining loads of
  configuration data in yaml.

### project guidelines

- contributions are extremely welcome - feedback, ideas, suggestions, bugs,
  documentation will be appreciated just as much as code.
- key criteria for code contributions are
  - 'Code LESS: every line creates a work-chain. Code is a liability, not an 
    asset'
  - think hard before adding dependencies
- upstream is at github because we need to build loads of stuff from github
  *anyway* and it's the easiest workflow/infrastructure for a small project.
  ybd will *remain* a small project.

### license

- license is GPLv2 but other licensing can be considered on request
- most of the copyright is currently Codethink but don't let that put you off.
  There's no intent to keep this as a Codethink-only project, nor will there be
  any attempt to get folks to sign a contributor agreement.
  contributors retain their own copyright.

