# brock

brock is an attempt to build on what we've learned from Morph, seeking
the following advantages:
- less functionality (just build, cache, deploy, trove)
  - drop morph branch|checkout|edit|merge
- drop workspaces
- much faster calculation of build-order, cache-keys
- aim to run on non-Linux environments (eg Mac OS)
- the words morphology, stratum, chunk disappear from the Baserock vocabulary
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
- be permissive and fast for day-to-day engineering, but still guarantee traceability and reproducibility
- a much smaller, much simpler codebase than we have with morph
- use existing software for the hard parts of distbuild (celery?)

- the initial idea is `brock build` replaces `morph build`
- then extend it to deal with multi-worker builds
- then follow on with brock deploy

## Some design notes

- for cache safety, we need to get to tree refs, ignore commit refs, tags, branches

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
  - so we need a separate assembly for morph, tbdiff, system-version-manager
  - add git to that, and ssh, and any other devtools?


      


