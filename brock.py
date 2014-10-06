import yaml

def load_assembly(foo):
  filename = "./sets/" + foo + ".def"

  text = ""

  try:
    with open(filename) as f:
       text = f.read()

  except:
	pass

  assembly = yaml.safe_load(text)
  return assembly

def get(thing, value):
	val = []
	try:
		val = thing[value]
	except:
		pass
	return val

def walk(name):
	this = load_assembly(name)
	print this['name']
	for dependency in get(this, 'depends'):

	    print '%s dependency is' % get(this, 'name')
	    walk(dependency)

	print '%s has chunks:' % get(this, 'name')
	for chunk in get(this, 'chunks'):
		print '%s with dependencies:' % get(chunk, 'name')
		print get(chunk, 'depends')

walk('third-set')

