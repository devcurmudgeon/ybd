check_cache_keys
----------------
Since ybd 15.44, the cache-key algorithm appears stable and can be
applied to definitions as far back as baserock-14.40.

So we can use the cache-keys as checksums to avoid regressions in the
algorithm. This doesn't matter much for the cache-key algorithm itself,
since it is versioned, but checking that we can get to these values also
confirms that we can still parse the old definitions files themselves.

baserock-14.40
v0: ci.6788f6634d42f0a42682bd2208cb123f69a157b4a50ac40108d91029558ec623
v1: ci.b9de86669ce182e60e3f9445e6394b478b67a2c73b4c0764491c158c5f2569e9

baserock-14.46
v0: ci.6357ea38e22bcbc3ebc399d36ed3bbfe03cab79079ab5b97096b7fc36e0e3351
v1: ci.99203daccc211d634102f94cab7095c7dae31c6daadc7541380d53e1b3b2fe8e

baserock-15.47.1
v0: ci.a809e39d26fea31b2dc674e190f6367a10cedaffe644775a59a93719cc5d5290
v1: ci.ce7f81b2e294c1893a08e4b18cf1d9a74f5e49bb58f7099ab55f656a05d887b4
