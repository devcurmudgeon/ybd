rm -fr ~/.brock/*
python brock.py test-definitions/fifth-set.def
ls  ~/.brock/cache/| sort > test-definitions/all-cache-names
echo '---------------'
echo 'Check'
git diff
pep8 brock.py
echo '---------------'
