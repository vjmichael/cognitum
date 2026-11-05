"""CH39 separate-UID independent MPFR certificate checker; no private signing keys.

Never trusts a worker's success flag, path, objective bound, or saved verifier
receipt. Re-reads sealed CH33 certificate and original CH23 inputs from its own
UID-restricted copies; replays all nodes and historical archive frames using MPFR.
This is independent execution of shared verifier code, NOT a different theorem
prover or an independent verifier implementation.
"""
from __future__ import annotations
import argparse,concurrent.futures,fcntl,multiprocessing,os,socketserver,sys,threading
from pathlib import Path
from protocol39 import HEX64,canonical,objhash,parse,peersock,safe_read,verify_attestation
from trust39 import private_directory,private_keyfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'CH_C14_35'))
from trust35 import witness_original_ch33

class CheckRequest(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            _,uid,_=peersock(self.request)
            if uid!=self.server.attestor_uid:raise PermissionError('Checker admits only attestor UID')
            msg=parse(self.rfile.readline(32769),32768)
            receipt=self.server.check(msg)
            self.wfile.write(canonical({'ok':True,'receipt':receipt})+b'\n')
        except Exception as exc:
            self.wfile.write(canonical({'ok':False,'error':type(exc).__name__})+b'\n')

class IndependentChecker(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
    daemon_threads=True;allow_reuse_address=False;request_queue_size=8
    def __init__(self,socket_path,*,private_root,source_root,proof_root,attestor_uid,math_uid,workers=2):
        if len({os.geteuid(),attestor_uid,math_uid})!=3:raise PermissionError('Checker must be independent UID')
        if not 1<=workers<=4:raise ValueError('Checker worker limit exceeded')
        private_root=Path(private_root);private_directory(private_root)
        private_keyfile(private_root/'frozen_pins.json')
        self.pins=parse(safe_read(private_root/'frozen_pins.json'))
        if len(self.pins)!=15:raise ValueError('Incomplete original-case policy')
        self.policy_sha=objhash(self.pins)
        self.attestor_uid=attestor_uid
        self.source_root=Path(source_root);self.proof_root=Path(proof_root)
        self.used=set();self.lock=threading.Lock();self.slots=threading.BoundedSemaphore(workers)
        self.pool=concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'))
        self.lockfd=os.open(private_root/'.checker.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        fcntl.flock(self.lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if Path(socket_path).exists():raise ValueError('Preexisting checker socket')
        super().__init__(str(socket_path),CheckRequest);os.chmod(socket_path,0o660)
    def check(self,msg):
        required={'op','case_id','nonce','policy_sha256','reported_attestation'}
        if type(msg)!=dict or set(msg)!=required or msg['op']!='check':raise ValueError('Checker request schema mismatch')
        case,nonce=msg['case_id'],msg['nonce']
        if type(case)!=str or case not in self.pins or type(nonce)!=str or not HEX64.fullmatch(nonce):
            raise ValueError('Non-frozen case or invalid challenge')
        if msg['policy_sha256']!=self.policy_sha:raise ValueError('Checker case policy mismatch')
        claimed=verify_attestation(msg['reported_attestation'],case,self.pins[case])
        with self.lock:
            if nonce in self.used:raise ValueError('Checker challenge replay')
            self.used.add(nonce)
        # This proof replay is indispensable: no cached, worker-provided, or hash-only result.
        with self.slots:
            actual=self.pool.submit(witness_original_ch33,case,self.source_root,self.proof_root,self.pins).result(timeout=900)
        verify_attestation(actual,case,self.pins[case])
        if actual!=claimed:raise ValueError('Independent MPFR result differs from worker report')
        value=objhash(actual)
        return {'version':1,'case_id':case,'nonce':nonce,'policy_sha256':self.policy_sha,
          'worker_attestation_sha256':objhash(claimed),'checker_attestation_sha256':value,
          'checker_result':'INDEPENDENT_REPLAY_ACCEPTED',
          'checker_scope':'FROZEN_CH23_127_NODES_6_FRAMES_MPFR_224'}
    def server_close(self):
        try:self.pool.shutdown(wait=True,cancel_futures=True)
        finally:super().server_close()

def main():
    p=argparse.ArgumentParser()
    for x in ('socket','private','source','proofs'):p.add_argument('--'+x,required=True)
    p.add_argument('--attestor-uid',type=int,required=True);p.add_argument('--math-uid',type=int,required=True)
    p.add_argument('--workers',type=int,default=2)
    a=p.parse_args();s=IndependentChecker(a.socket,private_root=a.private,source_root=a.source,
        proof_root=a.proofs,attestor_uid=a.attestor_uid,math_uid=a.math_uid,workers=a.workers)
    try:s.serve_forever(poll_interval=.2)
    finally:s.server_close()
if __name__=='__main__':main()