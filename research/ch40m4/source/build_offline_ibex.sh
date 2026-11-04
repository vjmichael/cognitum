#!/usr/bin/env bash
set -euo pipefail
# Build the officially downloaded IBEX source in an isolated working directory.
# Prerequisites: Debian 13 amd64, gcc/g++, cmake, Ninja, m4, Python3,
# and files passed from the uploaded IBEX and Flex/Bison bundles.
if [ "$#" -ne 3 ]; then
  echo "Usage: $0 IBEX_SOURCE_REPAIR.zip FLEX_BISON_PREREQS.zip TARGET_DIR" >&2; exit 2
fi
IBEX_ZIP="$(realpath "$1")"; PREREQ_ZIP="$(realpath "$2")"; TARGET="$(realpath -m "$3")"
mkdir -p "$TARGET";export TARGET IBEX_ZIP PREREQ_ZIP
python3 - <<'PY'
import zipfile,tarfile,hashlib,json,io,os,pathlib,subprocess
root=pathlib.Path(os.environ['TARGET'])
with zipfile.ZipFile(os.environ['IBEX_ZIP']) as z:
 m=json.loads(z.read('SOURCE_MANIFEST.json'))
 data=z.read('ibex-ibex-2.9.1-official-source.tar.gz')
 if hashlib.sha256(data).hexdigest()!=m['upstream_formula_sha256']:raise ValueError('IBEX source hash mismatch')
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as t:t.extractall(root/'sources',filter='data')
with zipfile.ZipFile(os.environ['PREREQ_ZIP']) as z:
 m=json.loads(z.read('manifest.json'))
 for record in m['files']:
  b=z.read(record['name'])
  if hashlib.sha256(b).hexdigest()!=record['sha256']:raise ValueError('deb SHA mismatch '+record['name'])
  deb=root/record['name'];deb.write_bytes(b)
  subprocess.run(['dpkg-deb','-x',str(deb),str(root/'debs')],check=True)
PY
SRC="$TARGET/sources/ibex-lib-ibex-2.9.1"
export PATH="$TARGET/debs/usr/bin:$PATH"
export BISON_PKGDATADIR="$TARGET/debs/usr/share/bison"
cmake -S "$SRC" -B "$TARGET/build" -G Ninja -DINTERVAL_LIB=filib -DLP_LIB=soplex -DCMAKE_BUILD_TYPE=Release
# Compatibility fix for old SoPlex 4.0.2 on GCC14: copy its 50-element array,
# rather than attempting an illegal raw C++ array assignment. Changes ONLY
# extracted build tree; official IBEX source archive is left untouched.
export H="$TARGET/build/lp_lib_wrapper/soplex/soplex-4.0.2/src/soplex/datahashtable.h"
python3 - <<'PY'
from pathlib import Path
import os
p=Path(os.environ['H']);s=p.read_text();needle='primes = base.primes;'
if s.count(needle)!=1:raise ValueError('unexpected vendor source; refuse patch')
p.write_text(s.replace(needle,'for (int pi=0; pi<50; ++pi) primes[pi] = base.primes[pi];'))
PY
cmake --build "$TARGET/build" -j 4
"$TARGET/build/bin/ibexopt" --version
