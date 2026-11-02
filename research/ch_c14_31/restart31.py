"""Fresh process re-establishes trust from original CH29 63-node certificate.

No checkpoint serialization, cache import, or receipt import is available.
A stored receipt/manifest can be inspected for provenance but is never proof.
"""
from __future__ import annotations
import argparse,json,os,sys,time
from pathlib import Path
D=Path(__file__).resolve().parent;sys.path.insert(0,str(D))
from verifier31 import ProgressiveVerifier,load_original_case
from prefix31 import project_prefix

def restart_chain(case_id):
    inp,proto,duals,archived=load_original_case(case_id)
    c63,_=archived(63);c127,record=archived(127)
    session=ProgressiveVerifier()
    verified=[]
    for size,cert in ((63,c63),(95,project_prefix(c127,95)),(127,c127)):
        r=session.verify_stage(cert,inp,{**proto,'node_budget_per_case':size},duals)
        verified.append({'nodes':size,'cpu_seconds':r['cpu_seconds'],
                         'fresh':r['receipt']['ancestor_caps_recomputed'],
                         'reused':r['receipt']['verified_prefix_nodes_reused'],
                         'gap_upper_display':r['receipt']['gap_upper_display'],
                         'cert_sha256_diagnostic':r['certificate_digest']})
    if abs(verified[-1]['gap_upper_display']-record['gap_upper_display'])>1e-10:
        raise AssertionError('Fresh process result disagrees with CH29 original full replay')
    return {'case_id':case_id,'pid':os.getpid(),'restart_reverified_from_scratch':63,
            'imported_cache':False,'chain':verified,'verified':True,
            'production_release':'NO_GO','unbounded_global_claim':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True)
    a=p.parse_args();print(json.dumps(restart_chain(a.case),sort_keys=True,allow_nan=False))
