import yaml

with open("./sets/second-set.def") as f:
    text = f.read()

obj = yaml.safe_load(text)
# print obj

for iter in obj['chunks']:
  print iter['lookup']
  print '****'
  print iter['depends']

print '----------------'
print obj['depends']