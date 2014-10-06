import yaml

def load_assembly(foo):
  filename = "./sets/" + foo + ".def"

  assembly = []

  try:
    with open(filename) as f:
       text = f.read()
  
    assembly = yaml.safe_load(text)

  except:
	return None

  return assembly

def get(thing, value):
	val = []
	try:
		val = thing[value]
	except:
		pass
	return val

def walk(name):
	print 'Walk %s' % name
	this = load_assembly(name)
	for dependency in get(this, 'build-depends'):
	    print '%s build-dependency is %s' % (get(this, 'name'), dependency)
	    walk(dependency)

	for content in get(this, 'contents'):
		print '%s contains %s, check for build-dependencies:' % (get(this, 'name'), get(content, 'name'))
		print '-- %s' % get(content, 'build-depends')
		if load_assembly(get(content, 'name')):
		    walk(get(content, 'name'))

walk('fourth-set')

