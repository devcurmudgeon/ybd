rm -fr ~/.ybd/caches/*
python ybd.py test-definitions/fifth-set.def
ls  ~/.ybd/cache/| sort > test-definitions/all-cache-names
echo '---------------'
echo 'Check'
git diff
pep8 *.py
echo '---------------'
