# rename morph: to name: and drop .morph extensions from all names
find . -name *morph | xargs sed -i -e "s/^- morph: strata\//- name: /"
find . -name *morph | xargs sed -i -e "s/^- morph: systems\//- name: /"
find . -name *morph | xargs sed -i -e "s/\.morph//"

# rename strata: and chunks: => components:
find . -name *morph | xargs sed -i -e "s/strata:/components:/"
find . -name *morph | xargs sed -i -e "s/chunks:/components:/"
find . -name *morph | xargs sed -i -e "/morph: /d"

# drop all lines containing empty build-depends
find . -name *morph | xargs sed -i -e "/build-depends: \[\]/d"

# drop all 'kind' lines
find . -name *morph | xargs sed -i -e "/kind: /d"

# drop all 'unpetrify' lines
find . -name *morph | xargs sed -i -e "/unpetrify \[\]/d"

# add target field for arm-specific chunks
#find . -name *morph | xargs sed -i -e 's/^\(- name:.*\)-\(armv7.*\)$/\1-\2!  target: \2/'

# add target field for x86-specific chunks
#find . -name *morph | xargs sed -i -e 's/^\(- name:.*\)-\(x86.*\)$/\1-\2!  target: \2/'

for i in `find . -name *morph`; do j=${i//\.morph/} ; mv $i $j.def ; done
for i in `find . -name *morph-e`; do rm $i ; done