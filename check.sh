echo
echo
set -v
rm -fr ~/.ybd/cache/ybd-artifacts/*
rm -fr ~/.ybd/staging/*
rm -fr /src/staging/*
# rm -fr /src/cache/ybd-artifacts/*
python ../ybd/ybd.py $1 $2
