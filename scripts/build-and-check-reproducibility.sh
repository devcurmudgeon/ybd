#!/bin/sh

set -e

if [ "$#" != "1" ]
then
    echo "Invalid # arguments"
    echo "Usage: ./build-and-check-reproducibility.sh definitions/systems/build-system-x86_64.morph"
    exit 1
fi

CURRENT_DIR=`pwd`

# This script is a quick way to automate the process of 
# running consecutive builds with ybd, getting SHA1 of built
# artifacts for each build and checking for differences in
# SHA1, which would indicate that a component is not reproducible.

build_system="$1"

DIR=$( dirname -- "$0" )
cd "$DIR"
cd ..

`grep -e artifacts ybd.def > artifact.def`
artifact_dir=`sed -e "s%artifacts: '%%" -e "s%'%%" artifact.def`

cd "$CURRENT_DIR"

if [ -f build1.shasum ]
then
    `rm build1.shasum`
fi
if [ -f build2.shasum ]
then
    `rm build2.shasum`
fi

echo "First build of system..."
python "$DIR/../ybd.py" "$build_system" x86_64 
ls -d "$artifact_dir"*.unpacked/ | grep -ve 'stage1' -e 'stage2' > artifacts.list
while read line
do
    find "$line" -type f -print0 | xargs -r0 sha1sum >> build1.shasum
done < artifacts.list
`mv "$artifact_dir" "$artifact_dir-tmp" && mkdir -p "$artifact_dir"`
echo "Second build of system..."
python "$DIR/../ybd.py" "$build_system" x86_64 
ls -d "$artifact_dir"*.unpacked/ | grep -ve 'stage1' -e 'stage2' > artifacts.list
while read line
do
    find "$line" -type f -print0 | xargs -r0 sha1sum >> build2.shasum
done < artifacts.list

echo "Contracting filenames to make the comparison more readable..."
cp build1.shasum build1.orig
sed -re "s%$artifact_dir%%" -e 's%\.[0-9a-f]+%%' -e 's%\.unpacked%\t%' -e 's%  %\t%' build1.orig > build1.clean

cp build2.shasum build2.orig
sed -re "s%$artifact_dir%%" -e 's%\.[0-9a-f]+%%' -e 's%\.unpacked%\t%' -e 's%  %\t%' build2.orig > build2.clean

echo "Sorting alphabetically by component..."
sort -k 2 build2.clean > build2.compare

`diff -u0 build1.compare build2.compare > diff.compare`
`cp diff.compare diff.orig`
`grep -ve '+++' -e '^\-' diff.orig > diff.compare`
`sed -re 's%\@@ \-[0-9]+ \+[0-9]+ \@@%%' -e 's%\@@ \-[0-9]+\,[0-9]+ \+[0-9]+\,[0-9]+ \@@%%' -e 's%\+[0-9a-f]+\t%%' diff.compare > diff.clean`

echo "Performing cleanup operations..."
`rm build*.c* build*.orig diff.compare diff.orig`

echo "List of differing components (no shasum) outputted to diff.clean"
