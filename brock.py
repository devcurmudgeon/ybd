import yaml

def load_def(name):
  filename = "./sets/" + name + ".def"

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

def graph_count(name):
	try:
	    graph[name] = graph[name] + 1

	except:
	    graph[name] = 0

def walk(name, graph):
	this = load_def(name)
	graph_count(name)

	needs = 0
	for dependency in get(this, 'build-depends'):
	    needs = needs + 1
	    graph_count(dependency)
	    walk(dependency, graph)

	for content in get(this, 'contents'):
		cname = get(content, 'name').split('|')[0]
		graph_count(cname)
		for dep in get(content, 'build-depends'):
		    graph_count(dep)
		if load_def(get(content, 'name')):
		    needs = needs + 1
		    walk(get(content, 'name'), graph)

	print '%s needs %s others' % (name, needs)

graph = {}
defs = ['first-set', 'second-set', 'third-set', 'fourth-set', 'fifth-set']
for i in defs:
    walk(i, graph)
    print graph


