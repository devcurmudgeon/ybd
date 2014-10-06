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
	for dependency in get(this, 'depends'):
	    print '%s dependency, depends on' % get(this, 'name')
	    walk(dependency)

	for chunk in get(this, 'chunks'):
		print '%s chunk with dependencies:' % get(chunk, 'name')
		print get(chunk, 'depends')
		if load_assembly(get(chunk, 'name')):
		    walk(get(chunk, 'name'))

walk('fourth-set')

