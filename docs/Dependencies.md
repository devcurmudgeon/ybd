## Dependencies

ybd requires git, gcc, make, autotools, python, tar, wget. Note that the
Baserock definitions also require gawk.

So for a Debian-based system:

    apt-get update; apt-get install build-essential gawk git m4

… and a Fedora-based system:

    yum install make automake gcc gcc-c++ kernel-devel git gawk m4

ybd also depends on [pyfilesystem](http://pyfilesystem.org),
[pyyaml](http://pyyaml.org/wiki/PyYAML),
[sandboxlib](https://github.com/CodethinkLabs/sandboxlib),
[requests](https://github.com/kennethreitz/requests),
and optionally [jsonschema](https://github.com/Julian/jsonschema).

To serve artifacts using kbas, it additionally requires
[bottle](https://github.com/bottlepy/bottle) and optionally
[cherrypy](https://github.com/cherrypy/cherrypy.git).

To use the Riemann functionality, it additionally requires
[riemann-client](https://github.com/borntyping/python-riemann-client).

If you trust the Python Package Index (PyPI) and pip is available on your
machine, you can install these dependencies with:

    pip install fs pyyaml sandboxlib requests jsonschema bottle cherrypy riemann-client

If you need to install pip itself:

    wget https://bootstrap.pypa.io/get-pip.py
    python get-pip.py
