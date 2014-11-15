# YBD
YBD aims to show improvements on/for morph:
- smaller, simpler codebase
- concentrate on core functionality
  - aiming for build, cache, deploy
  - no branch|checkout|edit|merge
- drop workspaces
- much faster calculation of build-order, cache-keys
- run on non-Linux environments (eg Mac OS)
- drop the words morph, morphology, stratum, chunk from the Baserock vocabulary
- instead just deal with generic definitions and components
  - a single definition may have components and build-dependencies
  - components is just a list
  - build-dependencies is just a list of components too
  - support for nested components
  - a component may contain no code (could be just videos for example)
  - a component may be a tarball
  - may have multiple versions of a component, eg
    - foo|aa and foo|bb installed
    - foo|cc and foo|dd used as build-dependencies by other component
- ability to build and deploy any level of component
  - an individual software component (what we've called chunks until now)
  - a logically-coupled set of components (what we've called strata)
  - a bootable collection of sets of components (what we've called systems)
- users can understand and diagnose the cache naming scheme
- permissive and fast for day-to-day engineering
- but still guarantee traceability and reproducibility

Notes:
- morph-converter.sh tweaks definitions.git to drop strata, systems, chunks etc.
- ybd.py can parses all of the definitions and walk the whole build tree
  in build order for any target definition within two seconds or so. 
- it has a working cache scheme, which is simpler and much faster than what morph does.
  All cache-keys can be calculated within a couple of seconds (once git repos are fetched)
- it doesn't build anything yet though.
