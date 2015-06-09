# ybd

ybd is a tool for integrating software stacks. it does four things:

- parse some yaml files describing integrated collections of software components
- collect the source for one target collection (from git repos)
- build the collection
- (optionally) deploy the collection

currently ybd understands the semantics of yaml
[definitions](http://git.baserock.org/cgi-bin/cgit.cgi/baserock/baserock/definitions.git/tree/)
from the [Baserock](http://wiki.baserock.org) project. ybd does some of the things that Baserock morph does, without most of the complexity that morph has
accrued since development started in 2011.

ybd can be a simple start-point for building, deploying, learning and
experimenting with definitions, algorithms and functionality on Baserock
projects. with a little work it can be used to build other stacks too.

the ybd codebase is currently only ~ 1560 lines of Python in ten source files.
even so ybd can reproducibly build all systems in Baserock's definitions.git,
i.e. all of the FOSS components required for Linux appliances up to and
including, for example

- self-hosting Linux development systems
- GENIVI baseline systems
- OpenStack appliances

it can also deploy some systems in some ways.

ybd is under development. things will change :)

### dependencies

currently ybd is for Linux only, and requires git, gcc, make, autotools,
linux-user-chroot, python, tar, wget.

ybd also depends on [pyyaml](http://pyyaml.org/wiki/PyYAML),
[sandboxlib](https://github.com/CodethinkLabs/sandboxlib),
and optionally Julian Berman's
[jsonschema](https://github.com/Julian/jsonschema)

if you trust the Python Package Index (PyPI) you can install them with:

```
    pip install pyyaml sandboxlib jsonschema
```

### quick start

```
    git clone git://github.com/devcurmudeon/ybd
    git clone git://git.baserock.org/baserock/baserock/definitions
    cd definitions
```

once there you can run

```
    ../ybd/ybd.py $1 $2
```

where

- $1 is relative path to a chunk, stratum, system or cluster definition file
- $2 is optional and specifies the architecture you're building/deploying for.

if you omit $2, ybd tries to use the architecture of your current machine
(x86_64 for most folks). note that all of the current baserock definitions
are for native builds, no cross-compile. so if you're on a typical laptop
it may be that your only option for $2 is `x86_64`

currently ybd generates a lot of log output, which hopefully helps to explain
what is happening. As we approach the singularity, most of the logging will
probably end up being turned off.

### comparison with morph

- morph does lots of things ybd can't do, and has lots of config options
- ybd has core functionality only - parse definitions, build, cache artifacts
- no branch|checkout|edit|merge (use git and be done)
- no need for workspaces
- no need to be in a baserock vm or a baserock chroot - ybd may even run on
other Linux operating systems (eg Ubuntu, fedora, debian) and maybe even
non-Linux operating systems (eg BSD, MacOS). However it may be have differently
and current Baserock definitions are Linux-specific.
- ybd has an order of magnitude less code, so
  - easier to try things, easier to change things, easier to debug things
  - less to break, less to maintain, less to audit
- ybd has minimal dependencies - just git and a 'normal' Linux toolchain
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
- remote cache appliance
- run without root privileges on non-Linux environments (eg Mac OS - needs a
  different isolation method instead of linux-user-chroot)
- test assumptions by creating definitions for other OS software sets, eg
  Aboriginal Linux and non-Linux systems
- test/fix to work on old versions of definitions, and on morphs.git
  (and separate out the idiosyncrasies, so code is tidy for future changes)
- command line syntax and args
- add some or all of ybd to definitions, as reference code to parse and build
  definitions.
- handle arch properly

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

