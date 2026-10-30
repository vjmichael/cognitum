"""Local, non-network Cognitum source/dependency/memory footprint probe.

Package source size excludes the interpreter and dependencies. Import delta is
an observation under this interpreter, *not* a packaged app memory guarantee.
"""
from __future__ import annotations
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import zipfile

PACKAGES=('protobuf','networkx','numpy','scipy','pandas','scikit-learn',
          'statsmodels','sympy','numba','cvxpy','causal-learn','dowhy')
ROOT=Path(__file__).resolve().parents[1]


def archive_footprint(p: Path):
    with zipfile.ZipFile(p) as z:
        files=[i for i in z.infolist() if not i.is_dir()]
        categories={}
        for i in files:
            key=i.filename.split('/',1)[0] if '/' in i.filename else '(root)'
            bucket=categories.setdefault(key,{'files':0,'uncompressed_bytes':0,'compressed_bytes':0})
            bucket['files']+=1
            bucket['uncompressed_bytes']+=i.file_size
            bucket['compressed_bytes']+=i.compress_size
        return {'archive_bytes':p.stat().st_size,'files':len(files),
                'uncompressed_bytes':sum(i.file_size for i in files),
                'categories':categories}


def package_sizes():
    result={}
    for name in PACKAGES:
        try:
            dist=importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            result[name]={'available':False}
            continue
        total=0
        for entry in (dist.files or []):
            try:
                item=dist.locate_file(entry)
                if item.is_file():total+=item.stat().st_size
            except OSError:pass
        result[name]={'available':True,'version':dist.version,'package_file_bytes':total}
    return result


MEMORY_CODE=r'''
import json, sys
sys.path.insert(0,sys.argv[1])
if sys.argv[2]!='baseline': __import__('cognitum.'+sys.argv[2])
try:
 with open('/proc/self/status') as f:
  v=next(int(line.split()[1])*1024 for line in f if line.startswith('VmRSS:'))
except (OSError,StopIteration):v=None
print(json.dumps({'resident_bytes':v}))
'''


def import_memory(module):
    def measure(label):
        p=subprocess.run([sys.executable,'-I','-c',MEMORY_CODE,str(ROOT),label],
                         capture_output=True,text=True,timeout=15,check=True)
        return json.loads(p.stdout)['resident_bytes']
    baseline=measure('baseline')
    selected=measure(module)
    return {'module':module,'baseline_resident_bytes':baseline,
            'import_resident_bytes':selected,
            'observed_delta_bytes':selected-baseline if baseline is not None and selected is not None else None,
            'note':'One warm-installed Python environment; not predicted Windows/edge RAM'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path)
    p.add_argument('--module',default='causal',choices=('causal','causal_estimation','causal_dowhy_backend'))
    args=p.parse_args(argv)
    out={'source_root':'relative to source tree',
         'size_warning':'Source-only numbers exclude interpreter, dependencies, models and caches',
         'distributions':package_sizes(),
         'memory_probe':import_memory(args.module)}
    if args.archive:out['archive']=archive_footprint(args.archive)
    print(json.dumps(out,indent=2,sort_keys=True))

if __name__=='__main__': main()
