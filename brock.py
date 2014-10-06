import yaml

def load_assembly(foo):
  filename = "./sets/" + foo + ".def"

  with open(filename) as f:
    text = f.read()

  assembly = yaml.safe_load(text)
  return assembly

obj = load_assembly("third-set")

for iter in obj['depends']:
  assembly = load_assembly(iter)
  print assembly['assembly']
  print '----------------'
  print assembly['depends']
  for chunk in assembly['chunks']:
    print chunk['lookup']
    print '===='
    print chunk['depends']

