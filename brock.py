import yaml
import os

DTR = 'DTR'

def load_def(name):
  filename = "./test-definitions/" + name + ".def"
  definition = []

  try:
    with open(filename) as f:
       text = f.read()
  
    definition = yaml.safe_load(text)

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

def assemble(name):
	print 'assemble %s' % name

def touch(pathname):
    with open(pathname, 'w'):
        pass

def cache_key(name):
	return "./cache/" + name + "|" + DTR + ".cache"

def cache(name):
	print 'cache %s' % name
	touch(cache_key(name))

def is_cached(name):
	return False

	if os.path.exists(cache_key(filename)):
		return True

	for cache in maybe_caches(name):
		ref = get_ref(cache)
		diff = git_diff(DTR, ref)
		if diff:
			for dependency in get(name, 'build-depends'):
				return


def build(name):
	if is_cached(name):
		print '%s is cached' % name
		return

	this = load_def(name)
	for dependency in get(this, 'build-depends'):
		build(dependency)

	# wait here for all the dependencies to complete 
	# how do we know what thata happens?

	for content in get(this, 'contents'):
		cname = get(content, 'name')
		build(cname)

	assemble(name)
	cache(name)

defs = ['first-set', 'second-set', 'third-set', 'fourth-set', 'fifth-set', 'sixth-set']
defs = ['first-set']

for i in defs:
	print '------------------------'
	print 'Running on %s' % i
	print '------------------------'
	build(i)
