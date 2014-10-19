# rename morph: to name: and drop .morph extensions from all names
find . -name *morph | xargs sed -i -e "s/^- morph: strata\//- name: /"
find . -name *morph | xargs sed -i -e "s/^- morph: systems\//- name: /"
find . -name *morph | xargs sed -i -e "s/\.morph//"

# rename strata: and chunks: => contents:
find . -name *morph | xargs sed -i -e "s/strata:/contents:/"
find . -name *morph | xargs sed -i -e "s/chunks:/contents:/"
find . -name *morph | xargs sed -i -e "/morph: /d"

# drop all lines containing empty build-depends
find . -name *morph | xargs sed -i -e "/build-depends: \[\]/d"

# add target field for arm-specific chunks
#find . -name *morph | xargs sed -i -e 's/^\(- name:.*\)-\(armv7.*\)$/\1-\2!  target: \2/'

# add target field for x86-specific chunks
#find . -name *morph | xargs sed -i -e 's/^\(- name:.*\)-\(x86.*\)$/\1-\2!  target: \2/'
