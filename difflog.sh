# cp /src/cache/artifacts/*$1*build-log /src/logs/morph-reference/
# sed -i 's|src/tmp/staging/[^/]*|STAGING|g' /src/logs/morph/*

cp /src/cache/ybd-artifacts/$1*build-log /src/logs/ybd
sed -i 's|src/staging/[^/]*/[^/]*|STAGING|g' /src/logs/ybd/$1*
diff /src/logs/morph-reference/*.$1* /src/logs/ybd/$1* | less