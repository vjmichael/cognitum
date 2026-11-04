import sys,time,json,statistics,hashlib
from pathlib import Path
from fractions import Fraction as F
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path[:0]=['/mnt/data/CH40M3/site','/mnt/data/CH40M2/source','/mnt/data/CH40J/source']
from frozen40m2 import load_cases
from flint_hadamard_regions import compute
from rational_kernel40d import direct_upper
cases=load_cases(Path('/mnt/data/CH40K/traces'),Path('/mnt/data/CH40K/CH40K_ACCEPTANCE.json'))
records=[]
for c in cases:
 n=max((n for n in c.certificate['nodes'] if not n.get('children')),key=lambda n:n['upper_bound_ceil_display'])
 t=time.process_time();a=compute(c.certificate,n['effective_box']);ta=time.process_time()-t
 t=time.process_time();b=direct_upper(c.certificate,n['effective_box']).hi;tb=time.process_time()-t
 records.append({'case':c.name,'trace_sha256':c.source_sha256,'leaf_id':n['id'],'flint_cpu_seconds':round(ta,6),'rational_cpu_seconds':round(tb,6),'flint_minus_reference_upper':float(a-b),'flint_upper_conservative':a>=b,'flint_tighter_than_historical_leaf':float(a)<n['upper_bound_ceil_display'],'comparison_notice':'Same valid upper-bound class, different implementations and rounding: not a matched solver benchmark'})
 print(c.name,'Arb',round(ta,3),'rational',round(tb,3),'diff',float(a-b),flush=True)
report={'protocol':'CH40-M3-HADAMARD-KERNEL-TIMING-V1','scientific_release':'NO_GO','cases':records,'all_conservative':all(r['flint_upper_conservative'] for r in records),'any_frozen_cap_improved':any(r['flint_tighter_than_historical_leaf'] for r in records),'total_flint_cpu_seconds':round(sum(r['flint_cpu_seconds'] for r in records),5),'total_rational_cpu_seconds':round(sum(r['rational_cpu_seconds'] for r in records),5),'note':'These are kernel CPU timings not matched end-to-end robust optimization results.'}
Path('/mnt/data/CH40M3/results/flint_vs_rational_cpu.json').write_text(json.dumps(report,indent=2)+'\n')

