# YBD
Having been a constant user of morph for a couple of years, and presented Baserock to quite a few people, I have some clear views about the strengths and weaknesses of the work we've done.

I'm very happy we can show fully traceability and repeatability, and that we've standardized on git, python, shell, yaml.

On the other hand I find the morph codebase extremely hard to understand, and I think our knowledge of the problem has evolved faster than we're moving the code.

In particular I'd like to see

- concentrate on core functionality (mainly build, cache, deploy, trove, mason)
  - drop morph branch|checkout|edit|merge
- drop workspaces
- faster calculation of build-order, cache-keys
- aim to run on non-Linux environments (eg Mac OS)
- drop the words morph, morphology, stratum, chunk from the Baserock vocabulary
- instead we just deal with components
  - a component definition may have components and build-dependencies
  - components is just a list of component
  - build-dependencies is just a list of component too
  - support for nested component
  - component may contain no code (could be just videos for example)
  - component can be a tarball
  - can have multiple versions of a component, eg
    - foo|aa and foo|bb installed
    - foo|cc and foo|dd used as build-dependencies by other component
- ability to build and deploy any level of component
  - an individual software component (what we've called chunks until now)
  - a logically-coupled set of components (what we've called strata)
  - a bootable collection of sets of components (what we've called systems)
- users can understand and diagnose the cache naming scheme
- permissive and fast for day-to-day engineering, but still guarantee traceability and reproducibility
- a smaller, simpler codebase than we have with morph

Notes:
- definitions.git are tweaked to drop strata, systems, chunks etc. The script I'm using for the tweaking is morph-converter.sh
- ybd.py parses all of the definitions directories and can walk the
  whole build tree for any component in build order within two seconds or so. It doesn't build anything yet though.
- It has a working cache scheme, which I think is simpler than what morph does
