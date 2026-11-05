"""Run immutable CH29 solver source, compare proof data with trace-patched copy."""
from __future__ import annotations
import sys,json,hashlib,argparse,pathlib,time
ROOT=pathlib.Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--trace',type=pathlib.Path,required=True);a=p.parse_args()
trace=json.loads(a.trace.read_text());case=trace['case'];n=trace['node_count']
base=ROOT/'source';d=base/'CH_C14_29'
sys.path[:0]=[str(d),str(base/'CH_C14_27'),str(base/'CH_C14_26'),str(base/'CH_C14_24')]
from solver29 import solve
proto=json.loads((d/'frozen_protocol.json').read_text());inp=json.loads((base/'CH_C14_25'/'inputs'/(case+'.json')).read_text())
duals=json.loads((base/'CH_C14_27'/'frozen_duals.json').read_text())[case]
t0=time.perf_counter();cert=solve(inp,{**proto,'node_budget_per_case':n},duals)
cert.update({'research_case_id':case,'original_case_sha256':proto['original_case_sha256'][case],
             'frozen_protocol_sha256':hashlib.sha256((d/'frozen_protocol.json').read_bytes()).hexdigest()})
reported=trace['certificate']
volatile={'solve_cpu_seconds','elapsed_seconds'}
for key in reported:
 if key in volatile:continue
 if json.dumps(cert.get(key),sort_keys=True)!=json.dumps(reported[key],sort_keys=True):
  raise AssertionError('INSTRUMENTED PRODUCER MUTATED ORIGINAL CERTIFICATE FIELD: '+key)
print('PASS historical uninstrumented vs observed source: all certificate proof fields identical',case,n,'nodes','seconds',round(time.perf_counter()-t0,2))