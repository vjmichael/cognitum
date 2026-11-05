"""CH40-G UID1004 independent checking service: fresh CH39 224-bit replay PLUS
fresh CH40-F independently implemented original CH29 160-bit MPFR cap trace.
Neither a saved receipt nor worker success report can substitute for either replay.
Research-only, no private signer/attestor key, SO_PEERCRED-enforced caller UID.
"""
from __future__ import annotations
import argparse,hashlib,pathlib
from checker39 import IndependentChecker
from caps_policy40g import PINNED,validate_caps
from research_receipt40f import checker_issue_after_live_replay

class IndependentCapsChecker(IndependentChecker):
    def __init__(self,socket_path,*,archive,trace_dir,**kw):
        self.archive=pathlib.Path(archive);self.trace_dir=pathlib.Path(trace_dir)
        super().__init__(socket_path,**kw)
        # Fail before serving if the root of mathematical trust was altered.
        from caps_policy40g import ORIGINAL_ARCHIVE_SHA256
        if hashlib.sha256(self.archive.read_bytes()).hexdigest()!=ORIGINAL_ARCHIVE_SHA256:
            raise ValueError('CH40-G original source trust anchor changed')
    def check(self,msg):
        # Reject untrusted/altered immutable trace source BEFORE costly verification.
        case=msg['case_id']
        if case not in PINNED:raise ValueError('No frozen source trace')
        trace=self.trace_dir/(case+'_127_original_mpfr_trace.json')
        if hashlib.sha256(trace.read_bytes()).hexdigest()!=PINNED[case]['trace_sha256']:
            raise ValueError('Trace differs from frozen producer source')
        # CH39 original pinned MPFR 224-bit nodes + archived history.
        original=super().check(msg)
        # CH40F independent Decimal/Fraction check of the actual 160-bit MPFR
        # producer trace; does not import/execute any historical solver function.
        research=checker_issue_after_live_replay(trace,self.archive,msg['nonce'],self.policy_sha)
        validate_caps(research,case,msg['nonce'],self.policy_sha,self.pins[case])
        return {'ch39_receipt':original,'cap_receipt':research}

def main():
    p=argparse.ArgumentParser()
    for n in ('socket','private','source','proofs','archive','traces'):p.add_argument('--'+n,required=True)
    for n in ('attestor-uid','math-uid'):p.add_argument('--'+n,type=int,required=True)
    p.add_argument('--workers',type=int,default=1)
    a=p.parse_args()
    s=IndependentCapsChecker(a.socket,private_root=a.private,source_root=a.source,
        proof_root=a.proofs,archive=a.archive,trace_dir=a.traces,
        attestor_uid=a.attestor_uid,math_uid=a.math_uid,workers=a.workers)
    try:s.serve_forever(poll_interval=.2)
    finally:s.server_close()
if __name__=='__main__':main()