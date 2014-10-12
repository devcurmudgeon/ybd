# Brock

Brock aims to build on what we've learned from Morph. As a result we can
hope for the following advantages:
- the words morphology and stratum can disappear from the Baserock lexicon
- no need for workspaces
- aim for Brock to run on non-Linux environments (eg Mac OS)
- support for nested components
- support for definitions without code
- straightforward to have multiple versions of a component
  - foo|aa and foo|bb installed
  - foo|cc and foo|dd used as build-dependencies by other components
- user can understand and diagnose the cache naming scheme
- smaller, simpler codebase
- more permissive, but still with traceability and reproducibility
- much faster calculation of build-order, cache-keys
- use of proven software for distbuild queues (celery?)

- the initial scope is only brock build, to replace morph build/distbuild
- then follow on with brock deploy

# Some design notes

From a given tree ref (full SHA1) for definitions.git (DTR) we know quite a lot:

- it identifies a ref: value for every content that we care about
- and refs for all the dependencies

- For any content
  - if ref: is a full SHA1, the DTR is enough to act as a cache key
  - if ref: is a unique short SHA1, the DTR is still enough
  - if it's a non-unique short SHA1, we could assume that the DTR resolves to the earliest instance
    - so later a non-unique short SHA1 which is not the earliest instance returns an error
      - later developers should notice the short SHA1 is not unique, use a longer one.
  - if we adopt ref-locking, we can infer full tree SHA1 from human-readable sub-refs
  - any tag or branch which is not ref-locked must be assumed not-reproducible outside current machine
    - we could easily parse all refs and warn on this
    - but we could stick a unique short-sha on the cache key.

- so DTR is a hash of the content and all its dependencies
  - it can probably be uniquely identified by short SHA1
  - if the short SHA is not unique, we can lengthen it until it is
  - could use ref-locking here too

- DTR is easily identifiable
  - so user can check whether a given cache contains artifacts relevant to their work

So if someone else clones that tree
- we could assume any cached artifacts with DTR are valid
- we could default to using/requiring the morph version from the DTR

Now what about when user makes a change? Which subset of artifacts can be assumed valid?
- if morph, content ref: and all dependencies ref:s are unchanged
  (if git diff shows no change to its ref or any dependencies)
  - cache is valid, but our new DTR is different
    - can make a symlink to the original version?
- if content or dependencies have been modified locally, we need to build
- if content or any dependency ref: has changed, we need to build

- name: <content>|<ref>

- for new user DTR vs a set of cache DTRs
  - walk build graph in build order
    - if none of my dependencies have been built (ie all dependent caches for this DTR are symlinks?)
      - for each available cache in time order
        - if git diff does not contain <this-content>
          - this cache is valid
            - use this cache, symlink it for this DTR

    - if no cache with this DTR
      - build this, cache with this DTR    

  - and we're done???

- caches whose DTR doesn't exist can be deleted

- clearly changing baserock tools should not lead to rebuilds of non-baserock contents
  - so we need a separate assembly/stratum for morph, tbdiff, system-version-manager
  - add git to that, and ssh, and any other devtools


      


