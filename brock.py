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

def walk(name, graph):
	print
	print
	print 'Walk %s' % name
	this = load_assembly(name)

	graph[name] = '1'

	for dependency in get(this, 'build-depends'):
	    print '%s build-dependency is %s' % (get(this, 'name'), dependency)
	    graph[dependency] = '1'
	    walk(dependency, graph)

	for content in get(this, 'contents'):
		print '%s contains %s, check for build-dependencies:' % (name, get(content, 'name'))
		graph[get(content, 'name')] = '1'
		print '-- %s' % get(content, 'build-depends')
		for dep in get(content, 'build-depends'):
		    graph[dep] = '1'
		if load_assembly(get(content, 'name')):
		    walk(get(content, 'name'), graph)

graph = {}
walk('fourth-set', graph)

print graph


