apt-get update
apt-get install build-essential python-dev gawk git m4
wget https://bootstrap.pypa.io/get-pip.py
python get-pip.py
pip install fs pyyaml requests jsonschema bottle cherrypy riemann-client
pip install sandboxlib

cd ..

if [ ! -d definitions ] ; then
    git clone http://git.baserock.org/git/baserock/baserock/definitions.git
fi
cd definitions

