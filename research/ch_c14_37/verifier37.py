"""Independent Linux UID mathematical verifier; NO access to witness signing key.

Only the signer UID can call its group-protected AF_UNIX socket. The verifier
replays original CH23/CH33 MPFR under its own UID and issues a verifier-key
signed, nonce-bound attestation; neither client can submit math/proof bytes.
"""
from __future__ import annotations
import argparse, base64, json, os, socketserver, threading, socket, struct, fcntl, sys, concurrent.futures, multiprocessing
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from protocol37 import (HEX64,V_DOMAIN,canonical,parse,safe_read,sha,objhash,peersock)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'CH_C14_35'))
from trust35 import witness_original_ch33, make_pins

class VerifierRequest(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            pid,uid,gid=peersock(self.request)
            if uid!=self.server.signer_uid:raise PermissionError('Verifier only admits distinct signing UID')
            raw=self.rfile.readline(4097)
            if len(raw)>4096:raise ValueError('Too many verifier request bytes')
            msg=parse(raw,4096)
            response=self.server.handle_message(msg)
            self.wfile.write(canonical({'ok':True,'ticket':response})+b'\n')
        except Exception as err:
            self.wfile.write(canonical({'ok':False,'error':type(err).__name__,'detail':str(err)[:140]})+b'\n')

class VerifierDaemon(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
    daemon_threads=True
    request_queue_size=8
    allow_reuse_address=False
    def __init__(self,socket_path,*,private_root,source_root,proof_root,signer_uid,workers=2):
        if os.geteuid()==signer_uid:raise PermissionError('Verifier may not share signer UID')
        if not (1<=workers<=4):raise ValueError('Verifier concurrency exceeds 4')
        private_root=Path(private_root)
        self.signer_uid=signer_uid
        self.source_root=Path(source_root);self.proof_root=Path(proof_root)
        from trust37 import private_directory,private_keyfile
        private_directory(private_root);private_keyfile(private_root/'verifier_secret.ed25519.pem')
        private_keyfile(private_root/'verifier_public.ed25519.pem')
        private_keyfile(private_root/'frozen_pins.json')
        self.key=serialization.load_pem_private_key(safe_read(private_root/'verifier_secret.ed25519.pem',4096),password=None)
        if not isinstance(self.key,Ed25519PrivateKey):raise ValueError('Invalid verifier key')
        self.public=safe_read(private_root/'verifier_public.ed25519.pem',4096)
        self.fp=sha(self.public)
        self.pins=parse(safe_read(private_root/'frozen_pins.json',65536))
        if len(self.pins)!=15:raise ValueError('Verifier frozen original case set incomplete')
        self.policy_sha=objhash(self.pins)
        self.slots=threading.BoundedSemaphore(workers)
        self.pool=concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'))
        self.committed_nonces=set()
        self.nonce_lock=threading.Lock()
        self.seized=os.open(private_root/'.verifier.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        fcntl.flock(self.seized,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if Path(socket_path).exists():raise ValueError('Refuse unsafe preexisting verifier socket')
        super().__init__(str(socket_path),VerifierRequest)
        os.chmod(socket_path,0o660)

    def handle_message(self,msg):
        if type(msg)!=dict or set(msg)!={'op','case_id','nonce','policy_sha256'} or msg['op']!='prove':
            raise ValueError('Verifier accepts only signed-scope case/nonce/policy requests')
        case=msg['case_id'];nonce=msg['nonce']
        if type(case)!=str or case not in self.pins or type(nonce)!=str or not HEX64.fullmatch(nonce):
            raise ValueError('Unknown case or malformed one-time challenge')
        if msg['policy_sha256']!=self.policy_sha:raise ValueError('Verifier and signer frozen policies differ')
        with self.nonce_lock:
            if nonce in self.committed_nonces:raise ValueError('Reused challenge refused')
            self.committed_nonces.add(nonce) # memory-only within process; signer ledger enforces durable uniqueness
        with self.slots:
            att=self.pool.submit(witness_original_ch33,case,self.source_root,self.proof_root,self.pins).result(timeout=900)
        body={'version':1,'nonce':nonce,'case_id':case,'policy_sha256':self.policy_sha,
              'verifier_fingerprint_sha256':self.fp,'attestation':att}
        signed=base64.b64encode(self.key.sign(V_DOMAIN+canonical(body))).decode('ascii')
        return {'body':body,'signature':signed}
    def server_close(self):
        try:self.pool.shutdown(wait=True,cancel_futures=True)
        finally:super().server_close()

def provision_verifier(store,source_root):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from protocol37 import sync_dir
    store=Path(store)
    if store.exists():raise FileExistsError('Verifier already provisioned')
    store.mkdir(mode=0o700)
    key=Ed25519PrivateKey.generate()
    priv=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    pub=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    pins=make_pins(source_root)
    if len(pins)!=15:raise ValueError('Original frozen case set incorrect')
    for name,raw in [('verifier_secret.ed25519.pem',priv),('verifier_public.ed25519.pem',pub),('frozen_pins.json',canonical(pins)+b'\n')]:
        fd=os.open(store/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    sync_dir(store)
    return {'verifier_fingerprint_sha256':sha(pub),'policy_sha256':objhash(pins)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--socket',required=True);p.add_argument('--private',required=True)
    p.add_argument('--source',required=True);p.add_argument('--proofs',required=True)
    p.add_argument('--signer-uid',required=True,type=int);p.add_argument('--workers',type=int,default=2)
    a=p.parse_args()
    server=VerifierDaemon(a.socket,private_root=a.private,source_root=a.source,proof_root=a.proofs,
                          signer_uid=a.signer_uid,workers=a.workers)
    try:server.serve_forever(poll_interval=.2)
    finally:server.server_close()

if __name__=='__main__':main()
