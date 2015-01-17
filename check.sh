echo
echo
set -v
rm -fr ~/.ybd/cache/ybd-artifacts/*
rm -fr ~/.ybd/staging/*
rm -fr /src/staging/*
rm -fr /src/tmp/*
# rm -fr /src/cache/ybd-artifacts/*
python /src/ybd/ybd.py $1 $2
