import yaml

def load_assembly(foo):
  filename = "./sets/" + foo + ".def"

  with open(filename) as f:
    text = f.read()

  assembly = yaml.safe_load(text)
  return assembly

obj = load_assembly("third-set")

def get_dependencies(foo):
	depends = []
	try:
		depends = foo['depends']
	except:
		pass
	return depends

for iter in get_dependencies(obj):
  this = load_assembly(iter)
  print '----------------'
  print this['assembly']
  print get_dependencies(this)
  for chunk in this['chunks']:
    print chunk['lookup']
    print 'Dependencies:'
    print get_dependencies(chunk)

