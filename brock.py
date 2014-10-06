import yaml

def load_assembly(foo):
  filename = "./sets/" + foo + ".def"
  print filename

  with open(filename) as f:
    text = f.read()

  assembly = yaml.safe_load(text)
  return assembly

obj = load_assembly("second-set")

for iter in obj['depends']:
  assembly = load_assembly(iter)

  print assembly['depends']
  print '----------------'
  for chunk in assembly['chunks']:
    print chunk['lookup']
    print '****' 
    print chunk['depends']

