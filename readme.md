# YBD

YBD does useful things with Baserock definitions, while avoiding most
of the complexity that morph has accrued since its development started in 2011.

YBD can be a simple start-point for building, deploying, learning and
experimenting with definitions, algorithms and functionality on Baserock
projects.

The ybd codebase is currently only ~ 1550 lines of Python in ten source files.
Even so ybd can reproducibly build all systems in Baserock's definitions.git,
i.e. all of the FOSS components required for Linux appliances up to and
including, for example

- self-hosting Linux development systems
- GENIVI baseline systems
- OpenStack appliances

It can also deploy some systems in some ways.

YBD is under development. Things will change :)

# Dependencies

Currently YBD is for Linux only, and is expecting git, GCC, Autotools, python, and pyyaml. 

YBD also depends on [sandboxlib](https://github.com/CodethinkLabs/sandboxlib), and optionally Julian Berman's [jsonschema](https://github.com/Julian/jsonschema)

If you trust the Python Package Index (PyPI) you can install sandboxlib with:

`pip install sandboxlib`

The same goes for jsonschema.

# Quick Start

`git clone git://git.baserock.org/baserock/baserock/definitions ; cd definitions`

Once there, you should be able to run

python path/to/ybd/ybd.py $1 $2

where

- $1 is relative path to a chunk, stratum, system or cluster definition file
- $2 is the architecture you're building/deploying for

Note that all of the current definitions only work for native builds, no
cross-compile, so if you're on a typical laptop your only option for $2 is
`x86_64`

Currently YBD generates a lot of log output, which hopefully helps to explain what is happening. As we approach the singularity, most of the logging will probably end up being turned off.

### comparison with morph

- morph does lots of things ybd can't do, and has lots of config options
- ybd has core functionality only - parse definitions, build, cache artifacts
- no branch|checkout|edit|merge (use git and be done)
- no need for workspaces
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

In no particular order, here's a list of things that may be interesting to try
doing to/with ybd:
- pip install (iiuc the only dependencies are python, pyyaml, git, tar, wget
  and linux-user-chroot)
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

- License is GPLv2 but other licensing can be considered on request
- most of the copyright is currently Codethink but don't let that put you off.
  There's no intent to keep this as a Codethink-only project, nor will there be
  any attempt to get folks to sign a contributor agreement.
  Contributors retain their own copyright.

