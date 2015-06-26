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

artifact_dir=`cd ~/.cache/ybd/artifacts && pwd`

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
ls -d "$artifact_dir"/*.unpacked/ | grep -ve 'stage1' -e 'stage2' > artifacts.list
while read line
do
    find "$line" -type f -print0 | xargs -r0 sha1sum >> build1.shasum
done < artifacts.list
`mv "$artifact_dir" "$artifact_dir-tmp" && mkdir -p "$artifact_dir"`
echo "Second build of system..."
python "$DIR/../ybd.py" "$build_system" x86_64 
ls -d "$artifact_dir"/*.unpacked/ | grep -ve 'stage1' -e 'stage2' > artifacts.list
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
sort -k 2 build1.clean > build1.compare
sort -k 2 build2.clean > build2.compare

`diff -u build1.compare build2.compare > diff.compare`
`cp diff.compare diff.orig`
`grep -ve '+++' -e '^\-' diff.orig > diff.compare`
`sed -re 's%\@@ \-[0-9]+ \+[0-9]+ \@@%%' -e 's%\@@ \-[0-9]+\,[0-9]+ \+[0-9]+\,[0-9]+ \@@%%' -e 's%\+[0-9a-f]+\t%%' diff.compare > diff.clean`
`comm -1 -2 build1.compare build2.compare > comparison.clean`
`echo "|----------|----------|" > diff.mdwn`
`sed -e 's%^%| %' -e 's%\t% | %' -e 's%$% |%' diff.clean >> diff.mdwn`
`echo "|----------|----------|" >> diff.mdwn`

echo "Performing cleanup operations..."
`rm build*.c* build*.orig diff.compare diff.orig artifacts.list`

diff_lines=`wc -l < diff.clean`
clean_lines=`wc -l < comparison.clean`
total_lines=`wc -l < build1.shasum`
diff=$( echo $diff_lines/$total_lines*100 | bc -l )
clean=$( echo $clean_lines/$total_lines*100 | bc -l )
diff_percent=`LC_ALL=C /usr/bin/printf "%.*f\n" 1 $diff`
clean_percent=`LC_ALL=C /usr/bin/printf "%.*f\n" 1 $clean`

echo "$clean_percent% of files are bit-for-bit reproducible (same SHA1); these can be found in comparison.clean"
echo "$diff_percent% of files differ; these can be found in diff.clean"
echo "List of non-reproducibles in wiki-friendly tabled format outputted to diff.mdwn"
