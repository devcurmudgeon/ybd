echo
echo
rm -fr ~/.ybd/cache/artifacts/*
rm -fr ~/.ybd/staging/*
python ../ybd/ybd.py $1
