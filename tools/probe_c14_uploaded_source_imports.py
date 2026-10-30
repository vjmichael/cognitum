"""Diagnostics only: attempt genuine imports from user-supplied source snapshots.

Not a package installation, exact-version proof, scientific-method execution or
Windows/Lu sandbox attestation. Does not alter third-party code or wheel metadata.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

SOURCES = {'dowhy': 'dowhy', 'econml': 'econml.dml',
           'causal-learn': 'causallearn.search.ConstraintBased.PC'}

def probe(vendor: Path, timeout: float = 15.0) -> list[dict]:
    out=[]
    for label, mod in SOURCES.items():
        root=vendor / label
        expr=("import importlib,sys;sys.path.insert(0,%r);"
              "importlib.import_module(%r);print('IMPORT_OK')" %(str(root),mod))
        # -I suppresses environment/user-site injections while running in the
        # explicitly chosen interpreter; never claim this establishes a sandbox.
        try:
            run=subprocess.run([sys.executable,'-I','-c',expr],text=True,
                capture_output=True,timeout=timeout,check=False)
            stderr=run.stderr.strip().splitlines()
            last=stderr[-1] if stderr else ''
            out.append({'package':label,'module':mod,'source_directory':str(root),
                        'import_success':run.returncode==0,
                        'reason': 'IMPORT_OK' if run.returncode==0 else last[:240],
                        'not_a_scientific_runtime_gate':True})
        except subprocess.TimeoutExpired:
            out.append({'package':label,'module':mod,'import_success':False,
                        'reason':'IMPORT_TIMEOUT','not_a_scientific_runtime_gate':True})
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vendor',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result={'schema':'cognitum.c14.source-import-probe.v1','python':sys.version.split()[0],
            'results':probe(args.vendor),'genuine_scientific_execution':'NOT_TESTED'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    for x in result['results']: print(x['package'],x['import_success'],x['reason'])

if __name__=='__main__':main()
