import yaml
import os
import sys
import hashlib

def load_def(path, name):
	global DTR
	definition = {}
	try:
		with open(path + "/" + name) as f:
			text = f.read()

		definition = yaml.safe_load(text)
		DTR = hashlib.sha256(path + "/" + name).hexdigest()[:8]
		definition['hash'] = DTR

	except:
		return None

	return definition

def get(thing, value):
	val = []
	try:
		val = thing[value]
	except:
		pass
	return val

def assemble(this):
	print 'assemble %s' % this

def touch(pathname):
    with open(pathname, 'w'):
        pass

def cache_key(this):
	if type(this) is str:
		return path + "/cache/" + this + "|" + DTR + ".cache"

	try:
		return path + "/cache/" + this['name'] + "|" + this['hash'] + ".cache"

	except:
		return path + "/cache/" + this['name'] + "|" + DTR + ".cache"

def cache(this):
	print 'cache %s' % this
	touch(cache_key(this))

def is_cached(this):
	if os.path.exists(cache_key(this)):
		return True

	return False

	for cache in maybe_caches(this):
		ref = get_ref(cache)
		diff = git_diff(DTR, ref)
		if diff:
			for dependency in this['build-depends']:
				return

def build(this):
	print 'build %s' % this
	if is_cached(this):
		print '%s is cached' % this
		return

	for dependency in get(this, 'build-depends'):
		build(dependency)

	# wait here for all the dependencies to complete 
	# how do we know when that happens?

	for content in get(this, 'contents'):
		build(content)

	assemble(this)
	cache(this)

path, target = os.path.split(sys.argv[1])
build(load_def(path, target))
