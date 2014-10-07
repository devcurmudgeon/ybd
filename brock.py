import yaml
import os

def load_def(name):
  filename = "./sets/" + name + ".def"
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

def cache(name):
	print 'cache %s' % name
	filename = "./cache/" + name + ".cache"
	touch(filename)

def is_cached(name):
	filename = "./cache/" + name + ".cache"
	return os.path.exists(filename)

def build(name):
	this = load_def(name)
	if is_cached(name):
		print '%s is cached' % name
		return

	for dependency in get(this, 'build-depends'):
		build(dependency)

	for content in get(this, 'contents'):
		cname = get(content, 'name').split('|')[0]
		build(cname)

	assemble(name)
	cache(name)

defs = ['first-set', 'second-set', 'third-set', 'fourth-set', 'fifth-set', 'sixth-set']
for i in defs:
	print '------------------------'
	print 'Running on %s' % i
	print '------------------------'
	build(i)
