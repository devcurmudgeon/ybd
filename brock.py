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

	for chunk in get(this, 'chunks'):
		print '%s contains %s which has build-dependencies:' % (get(this, 'name'), get(chunk, 'name'))
		print '-- %s' % get(chunk, 'build-depends')
		if load_assembly(get(chunk, 'name')):
		    walk(get(chunk, 'name'))

walk('fourth-set')

