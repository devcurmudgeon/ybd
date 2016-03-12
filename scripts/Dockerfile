FROM ubuntu

# install dependencies
RUN apt-get update && \
    apt-get install -y build-essential gawk git m4 wget python

# install pip
WORKDIR $HOME
RUN wget https://bootstrap.pypa.io/get-pip.py && \
    python get-pip.py && rm get-pip.py

# install python dependencies
RUN pip install fs pyyaml sandboxlib requests jsonschema bottle cherrypy
