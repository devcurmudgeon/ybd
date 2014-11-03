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
- instead we just deal with content
  - a content definition may have contents and build-dependencies
  - contents is just a list of content
  - build-dependencies is just a list of content too
  - support for nested content
  - content may contain no code (could be just videos for example)
  - content can be a tarball
  - can have multiple versions of a piece of content, eg
    - foo|aa and foo|bb installed
    - foo|cc and foo|dd used as build-dependencies by other content
- ability to build and deploy any level of content
  - an individual software component (what we've called chunks til now)
  - a logically-coupled set of components (what we've called strata)
  - a bootable collection of sets of components (what we've called systems)
- users can understand and diagnose the cache naming scheme
- permissive and fast for day-to-day engineering, but still guarantee traceability and reproducibility
- a much smaller, much simpler codebase than we have with morph

Most of these ideas have been discussed in public and/or at Codethink and/or with customers, but it seems we're struggling to attack the changes given our existing commitments and codebase.

Being on the road for the last couple of weeks, and seeing how long it was taking to build the various dependencies for some of the GENIVI work, I found time to do some exploratory hacking, and offer the following starter code for consideration.

http://github.com/devcurmudgeon/ybd/ybd.py

Depending on reactions, I hope that it'll either inspire morph wizards to fix some of the above in morph, or maybe we could bring the hard stuff from morph into ybd? I'd prefer the latter, as I think it would help us to lose some of the cruft we've acquired, but I'm sure others will disagree. 

Anyways, I'm out of the office for a while, so I won't hear any of the cries, whether they be joy or rage :)

Notes:
- definitions.git are tweaked to drop strata, systems, chunks etc. The script I'm using for the tweaking is morph-converter.sh
- ybd.py parses all of the definitions directories and can walk the
  whole build tree for any component in build order within two seconds or so. It doesn't fetch or build anything yet though.
- It has a notional working cache scheme, but Emmet has already highlighted it's not safe - I'd welcome input/help on that (note I have so far been unable to understand morph's cache key scheme)
