"""Read-only CH30 provenance, data-integrity, and incremental equivalence audit.

For complete mathematical rechecks, rerun benchmark30.py. Saved measurements
are receipts, never sufficient in themselves to claim mathematical verification.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
D=Path(__file__).resolve().parent;BASE=D.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def audit(resultfile):
    protocol=json.loads((D/'frozen_protocol.json').read_text())
    orig=json.loads((BASE/'CH_C14_29/frozen_protocol.json').read_text())
    assert sha(D/'frozen_protocol.json')==(D/'frozen_protocol.sha256').read_text().split()[0]
    assert sha(BASE/'CH_C14_29/frozen_protocol.json')==protocol['historical_protocol_sha256']
    result=json.loads(resultfile.read_text())
    ids=set(orig['original_case_sha256']);observed=set()
    assert result['protocol_sha256']==sha(D/'frozen_protocol.json')
    for case in result['per_case']:
        cid=case['case_id'];assert cid in ids and cid not in observed;observed.add(cid)
        path=BASE/'CH_C14_25/inputs'/(cid+'.json')
        assert sha(path)==orig['original_case_sha256'][cid]
        source=json.loads(path.read_text());assert source['original_CH23_identity']==case['identity']
        assert case['node_reuse_127']==63 and case['fresh_nodes_127']==64
        assert case['status']=='REPLAYED_BUT_UNRESOLVED'
        assert case['pass'] is True and case['baseline_127_gap']>0.05
        for budget,name in ((63,'baseline_63_gap'),(127,'baseline_127_gap')):
            certpath=BASE/'CH_C14_29/runs/fixed'/str(budget)/'certificates'/(cid+'.json')
            archive=BASE/'CH_C14_29/runs/fixed'/str(budget)/'verifications'/(cid+'.json')
            vr=json.loads(archive.read_text());assert vr['certificate_sha256']==sha(certpath)
            assert abs(vr['gap_upper_display']-case[name])<1e-10
    assert len(observed)==result['cohort_size']
    if result['cohort_size']==len(ids):assert observed==ids
    assert result['global_certificates']==0
    assert result['total_reused_mpfr_caps']==63*len(observed)
    assert result['total_fresh_mpfr_caps']==64*len(observed)
    assert result['speedup_incremental_step_vs_cold_127']>0
    print('AUDIT PASS',len(observed),'original cases; 63 verified prefix nodes/case, 64 new node replays/case; scientific NO-GO')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('resultfile',type=Path,nargs='?',default=D/'benchmark_results.json')
    audit(p.parse_args().resultfile)