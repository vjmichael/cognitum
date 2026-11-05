"""CH31 progressive process-local verification and restart fail-closed policy.

No unverified serialized state is ever accepted.  A new process must first
replay a source certificate fully at >=224-bit MPFR, then may incrementally
verify extensions within that process. The results are finite-box proofs only.
"""
from __future__ import annotations
import hashlib,json,sys,time
from pathlib import Path
D=Path(__file__).resolve().parent; BASE=D.parent
sys.path.insert(0,str(BASE/'CH_C14_30'))
from verifier30 import VerifiedSession

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _seal_name(cert):
    # Diagnostic hash, never trusted as a substitute for mathematical replay.
    b=json.dumps(cert,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return hashlib.sha256(b).hexdigest()

class ProgressiveVerifier:
    """One CH29 proof chain. No checkpoint state import/export method."""
    __slots__=('_session','_last_n','_case_id','_last_cap')
    def __init__(self):
        self._session=VerifiedSession();self._last_n=0
        self._case_id=None;self._last_cap=None

    def verify_stage(self,cert,inp,proto,duals):
        n=len(cert['nodes'])
        if n<=self._last_n:raise ValueError('Non-growing or replayed stage; start a fresh verifier')
        cid=cert.get('research_case_id')
        if not cid or (self._case_id is not None and cid!=self._case_id):
            raise ValueError('Case cannot change within a verified chain')
        if proto.get('node_budget_per_case')!=n:
            raise ValueError('Protocol stage node budget must equal certificate node count')
        tick=time.process_time()
        # Critical: CH30 independently replays every node not in the validated
        # prefix, recomputes MPFR ancestor caps, and checks the full partition.
        receipt=self._session.verify(cert,inp,proto,duals)
        if (receipt['ancestor_caps_recomputed']!=n-self._last_n or
            receipt['verified_prefix_nodes_reused']!=self._last_n or
            receipt['release']!='NO_GO' or receipt['unbounded_global_claim'] is not False):
            raise ValueError('Unexpected incremental proof receipt')
        if self._last_cap is not None and receipt['gap_upper_display']>self._last_cap+1e-10:
            # Projection uses possibly different feasible incumbents, so this
            # check is intentionally limited to an *identical* retained incumbent
            # in the milestone driver, not a general theorem about every chain.
            raise ValueError('Upper objective-gap regression across frozen chain')
        self._last_n=n;self._case_id=cid;self._last_cap=receipt['gap_upper_display']
        return {'case_id':cid,'nodes':n,'cpu_seconds':time.process_time()-tick,
                'certificate_digest':_seal_name(cert),'receipt':receipt,
                'state_policy':'in_memory_only_and_recomputed_on_fresh_process'}

def load_original_case(case_id):
    historical=BASE/'CH_C14_29'
    p=historical/'frozen_protocol.json'
    protocol=json.loads(p.read_text())
    if sha(p)!=(historical/'frozen_protocol.sha256').read_text().split()[0]:
        raise ValueError('Historical CH29 protocol SHA invalid')
    if case_id not in protocol['original_case_sha256']:raise ValueError('Unknown original case')
    ipath=BASE/'CH_C14_25/inputs'/(case_id+'.json')
    if sha(ipath)!=protocol['original_case_sha256'][case_id]:
        raise ValueError('Original CH23 dataset digest invalid')
    dpath=BASE/'CH_C14_27/frozen_duals.json'
    if sha(dpath)!=protocol['original_dual_sha256']:raise ValueError('Original dual digest invalid')
    inp=json.loads(ipath.read_text());duals=json.loads(dpath.read_text())[case_id]
    def archived(n):
        cp=historical/'runs/fixed'/str(n)/'certificates'/(case_id+'.json')
        vr=historical/'runs/fixed'/str(n)/'verifications'/(case_id+'.json')
        if not cp.is_file() or not vr.is_file():raise ValueError('Missing original source proof')
        certificate=json.loads(cp.read_text());receipt=json.loads(vr.read_text())
        if receipt['certificate_sha256']!=sha(cp):raise ValueError('CH29 certificate changed')
        if certificate['original_case_sha256']!=protocol['original_case_sha256'][case_id]:
            raise ValueError('CH29 certificate identity mismatch')
        return certificate,receipt
    return inp,protocol,duals,archived