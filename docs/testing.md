check_parsing
-------------
YBD aims to normalise definitions into a more understandable representation.
With the addition of 'parse-only' mode, ybd can dump this representation as
json, and we can confirm there is no unexpected data.

FIXME: identify at least one valid test-case here.

check_cache_keys
----------------
Since ybd 15.44, the cache-key algorithm appears stable and can be
applied to definitions as far back as baserock-14.40.

So we can use the cache-keys as checksums to avoid regressions in the
algorithm. This doesn't matter much for the cache-key algorithm itself,
since it is versioned, but checking that we can get to these values also
confirms that we can still parse the old definitions files themselves.

```
    baserock-14.40
    0: ci.6788f6634d42f0a42682bd2208cb123f69a157b4a50ac40108d91029558ec623
    1: ci.b9de86669ce182e60e3f9445e6394b478b67a2c73b4c0764491c158c5f2569e9

    baserock-14.46
    0: ci.6357ea38e22bcbc3ebc399d36ed3bbfe03cab79079ab5b97096b7fc36e0e3351
    1: ci.99203daccc211d634102f94cab7095c7dae31c6daadc7541380d53e1b3b2fe8e

    baserock-15.47.1
    0: ci.a809e39d26fea31b2dc674e190f6367a10cedaffe644775a59a93719cc5d5290
    1: ci.ce7f81b2e294c1893a08e4b18cf1d9a74f5e49bb58f7099ab55f656a05d887b4
```

check splits
------------
We reduce the size of systems artifacts by installing a only subset of the
outputs from the builds during the assembly process. The code for this
is mainly in splitting.py, and involves applying regex expressions to the
artifacts, based on the definitions and default split-rules, during the
'install-stratum-artifacts' step.

For a given checkout of definitions, the generated files in a system should
be the same for all future versions of ybd, so we can checksum a known-good
list of generated files, and compare new runs against it as a regression test.

The best candidate is minimal-system, since this expressly makes use of a lot
of splitting. The proposed test case is from Richard Dale's original commit
of the split functionality...

```
    artifact-version: omitted
    definitions version: baserock-15.47.1
    ybd version: rdale/150-master-splitting
    cache-key: minimal-system-x86_64-generic.5315fd18ea98cd105d8b2890fcfff2faab6a8961800442a29643110c460dd810
    command: cat baserock/* | grep \/ | sort  | wc -l
      result: 559
    command: cat baserock/* | grep \/ | sort  | md5sum
      result: 6c3c9ad75990b93e1927012928444b83
    find . -type f | sort | wc -l
      result: 155
```

But we should also test (say) devel-system...

```
    artifact-version: omitted
    definitions version: baserock-15.47.1
    ybd version: rdale/150-master-splitting
    cache-key:  devel-system-x86_64-generic.be1eadec42172b8ddf41b7cfffc75e796f5642a3e7c43bdcbf161977d3995050
    command: cat baserock/* | grep \/ | sort  | wc -l
      result: 78818
    command: cat baserock/* | grep \/ | sort  | md5sum
      result: 9d5c8a7f1b6926b81ef1c8f94f3e194d
    find . -type f | sort | wc -l
      result: 75953
    find . -type f | sort | md5sum
      result: 5c6e4561557d319059986c161565f4bf

```

The above was achieved on AWS