"""CH38 Linux mathematical verifier, UID 1002: no signing key or signing APIs.

Answers only to the separate attestor UID 1003 over group-gated AF_UNIX + SO_PEERCRED.
The verifier replays original CH23 224-bit MPFR proofs; output is UNTRUSTED
until independently checked by attestor against its frozen case policy.
"""
from __future__ import annotations
import argparse, concurrent.futures, fcntl, multiprocessing, os, socketserver, sys, threading
from pathlib import Path
from protocol38 import HEX64,canonical,parse,safe_read,objhash,peersock
from trust38 import private_directory,private_keyfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'CH_C14_35'))
from trust35 import witness_original_ch33

class MathRequest(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            _,uid,_=peersock(self.request)
            if uid!=self.server.attestor_uid:raise PermissionError('Math service only accepts attestor UID')
            raw=self.rfile.readline(4097)
            if len(raw)>4096:raise ValueError('Oversized request')
            result=self.server.prove(parse(raw,4096))
            self.wfile.write(canonical({'ok':True,'result':result})+b'\n')
        except Exception as ex:
            self.wfile.write(canonical({'ok':False,'error':type(ex).__name__})+b'\n')

class MathDaemon(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
    daemon_threads=True;allow_reuse_address=False;request_queue_size=8
    def __init__(self,socket_path,*,private_root,source_root,proof_root,attestor_uid,workers=2):
        if os.geteuid()==attestor_uid:raise PermissionError('Verifier must be different UID from attestor')
        if not (1<=workers<=4):raise ValueError('At most four MPFR workers')
        private_root=Path(private_root);private_directory(private_root)
        private_keyfile(private_root/'frozen_pins.json')
        self.pins=parse(safe_read(private_root/'frozen_pins.json'))
        if len(self.pins)!=15:raise ValueError('Incomplete original case policy')
        self.policy_sha=objhash(self.pins);self.attestor_uid=attestor_uid
        self.source_root=Path(source_root);self.proof_root=Path(proof_root)
        self.used=set();self.nonce_lock=threading.Lock();self.slots=threading.BoundedSemaphore(workers)
        self.pool=concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'))
        self.seized=os.open(private_root/'.math.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        fcntl.flock(self.seized,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if Path(socket_path).exists():raise ValueError('Preexisting math socket')
        super().__init__(str(socket_path),MathRequest);os.chmod(socket_path,0o660)
    def prove(self,msg):
        if type(msg)!=dict or set(msg)!={'op','case_id','nonce','policy_sha256'} or msg['op']!='prove':
            raise ValueError('Invalid verifier request schema')
        case=msg['case_id'];nonce=msg['nonce']
        if type(case)!=str or case not in self.pins or type(nonce)!=str or not HEX64.fullmatch(nonce):
            raise ValueError('Unfrozen case or invalid nonce')
        if msg['policy_sha256']!=self.policy_sha:raise ValueError('Frozen policy disagreement')
        with self.nonce_lock:
            if nonce in self.used:raise ValueError('Repeated math challenge')
            self.used.add(nonce)
        with self.slots:
            att=self.pool.submit(witness_original_ch33,case,self.source_root,self.proof_root,self.pins).result(timeout=900)
        return {'version':1,'case_id':case,'nonce':nonce,'policy_sha256':self.policy_sha,'attestation':att}
    def server_close(self):
        try:self.pool.shutdown(wait=True,cancel_futures=True)
        finally:super().server_close()

def main():
    p=argparse.ArgumentParser()
    for x in ('socket','private','source','proofs'):p.add_argument('--'+x,required=True)
    p.add_argument('--attestor-uid',type=int,required=True);p.add_argument('--workers',type=int,default=2)
    a=p.parse_args();s=MathDaemon(a.socket,private_root=a.private,source_root=a.source,proof_root=a.proofs,
        attestor_uid=a.attestor_uid,workers=a.workers)
    try:s.serve_forever(poll_interval=.2)
    finally:s.server_close()
if __name__=='__main__':main()
