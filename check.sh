rm test-definitions/cache/*
python brock.py test-definitions/fifth-set.def
ls test-definitions/cache/| sort > test-definitions/all-cache-names
echo '---------------'
echo 'Check'
git diff
pep8 *.py
echo '---------------'
