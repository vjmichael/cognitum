"""Run the original source-pinned CH29 MPFR producer with passive trace taps.

No proof of correct optimized bounds is inferred from the producer trace alone.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,sys,time
from prepare40e import instrument,sha,PIN
ROOT=pathlib.Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--archive',type=pathlib.Path,required=True)
 p.add_argument('--case',default='one_event_n80_i00');p.add_argument('--nodes',type=int,choices=(1,7,15,31,63,127),default=1)
 p.add_argument('--result-dir',type=pathlib.Path,default=ROOT/'results');p.add_argument('--workspace',type=pathlib.Path,default=ROOT/'producer_workspace');p.add_argument('--reuse-workspace',action='store_true');a=p.parse_args()
 if a.case not in ['one_event_n80_i00','one_event_n160_i00','quasi_separated_n160_i00','quasi_separated_n80_i00','rare_1pct_n160_i00','rare_1pct_n160_i13','rare_1pct_n80_i00','rare_5pct_n160_i00','rare_5pct_n80_i00','zero_balanced_n160_i00','zero_balanced_n80_i00','zero_imbalanced_n160_i00','zero_imbalanced_n160_i05','zero_imbalanced_n160_i07','zero_imbalanced_n80_i00']:
  raise ValueError('Unregistered case')
 if sha(a.archive.read_bytes())!=PIN:raise ValueError('External original archive hash mismatch')
 if not a.reuse_workspace:instrument(a.workspace,a.archive)
 sys.path[:0]=[str(a.workspace/'CH_C14_29'),str(a.workspace/'CH_C14_27'),str(a.workspace/'CH_C14_26'),str(a.workspace/'CH_C14_24')]
 from solver29 import solve
 from producer_trace40e import NODES
 d=a.workspace/'CH_C14_29'; proto=json.loads((d/'frozen_protocol.json').read_text())
 inp_path=a.workspace/'CH_C14_25'/'inputs'/(a.case+'.json')
 if sha(inp_path.read_bytes())!=proto['original_case_sha256'][a.case]:raise ValueError('Original input digest mismatch')
 inp=json.loads(inp_path.read_text());dual_path=a.workspace/'CH_C14_27'/'frozen_duals.json'
 if sha(dual_path.read_bytes())!=proto['original_dual_sha256']:raise ValueError('Frozen dual digest mismatch')
 duals=json.loads(dual_path.read_text())[a.case]
 if inp['bounds']!=proto['original_root_box']:raise ValueError('Root box mismatch')
 cfg={**proto,'node_budget_per_case':a.nodes}
 t=time.perf_counter();cert=solve(inp,cfg,duals)
 if len(NODES)!=len(cert['nodes']):raise RuntimeError('Missing original producer node trace')
 if any(n['id']!=i or n['display_effective']!=cert['nodes'][i]['upper_bound_ceil_display'] for i,n in enumerate(NODES)):
  raise RuntimeError('Observer changed producer/source record')
 cert.update({'research_case_id':a.case,'original_case_sha256':proto['original_case_sha256'][a.case],
              'frozen_protocol_sha256':sha((d/'frozen_protocol.json').read_bytes())})
 patch=json.loads((a.workspace/'CH40E_PRODUCER_PATCH_MANIFEST.json').read_text())
 result={'protocol':'CH40E-ORIGINAL-MPFR-TRACE-V1','claim_scope':'SOURCE_TRACED_FINITE_ROOT_ONLY','case':a.case,
         'original_archive_sha256':PIN,'original_case_sha256':proto['original_case_sha256'][a.case],
         'original_protocol_sha256':sha((d/'frozen_protocol.json').read_bytes()),
         'producer_source_sha256':patch['instrumented_solver_sha256'],
         'coupled_source_sha256':patch['instrumented_coupled_sha256'],'precision_bits':proto['precision_bits'],
         'node_count':len(NODES),'nodes':NODES,'certificate_sha256':sha(json.dumps(cert,sort_keys=True,separators=(',',':')).encode()),
         'certificate':cert,'run_wall_seconds':round(time.perf_counter()-t,3),
         'scientific_release':'NO_GO','optimized_cap_independently_certified':False}
 a.result_dir.mkdir(parents=True,exist_ok=True)
 name=f'{a.case}_{a.nodes}_original_mpfr_trace.json';tmp=a.result_dir/(name+'.tmp');dest=a.result_dir/name
 tmp.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n');tmp.replace(dest)
 print('ORIGINAL MPFR FINISHED',a.case,len(NODES),'nodes','coupled methods',sum(n['method']=='coupled_logdet_dual' for n in NODES),'seconds',result['run_wall_seconds'],'file',dest,flush=True)
if __name__=='__main__':main()