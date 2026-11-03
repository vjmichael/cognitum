"""CH39 attestor UID 1003 requires independent checker UID 1004 before signing.

The attestor never reads proof files or runs MPFR. A worker report is
insufficient; the checker independently replays the pinned certificate and
archived history using its own sealed original source. The checker receipt
is included in the Ed25519-signed ticket. This is independent execution of
shared verification code, not a second mathematical implementation.
"""
from __future__ import annotations
import argparse, base64, fcntl, os, socket, socketserver, threading
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from protocol39 import HEX64,V_DOMAIN,canonical,parse,peersock,safe_read,objhash,sha,verify_attestation,verify_checker_receipt,receive_line,sync_dir
from trust39 import private_directory,private_keyfile

def math_request(path,body,uid,timeout=900):
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(timeout)
    try:
        s.connect(str(path));_,peer_uid,_=peersock(s)
        if peer_uid!=uid:raise PermissionError('Untrusted mathematical-service process UID')
        s.sendall(canonical(body)+b'\n');return receive_line(s,32768)
    finally:s.close()

class AttestorRequest(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            _,uid,_=peersock(self.request)
            if uid!=self.server.signer_uid:raise PermissionError('Attestor only accepts witness signer UID')
            raw=self.rfile.readline(4097)
            if len(raw)>4096:raise ValueError('Oversized attestor request')
            ticket=self.server.prove(parse(raw,4096))
            self.wfile.write(canonical({'ok':True,'ticket':ticket})+b'\n')
        except Exception as ex:
            self.wfile.write(canonical({'ok':False,'error':type(ex).__name__})+b'\n')

class AttestorDaemon(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
    daemon_threads=True;allow_reuse_address=False;request_queue_size=8
    def __init__(self,socket_path,*,private_root,math_socket,checker_socket,math_uid,checker_uid,signer_uid):
        if len({os.geteuid(),math_uid,checker_uid,signer_uid})!=4:raise PermissionError('Attestor UID must be unique')
        root=Path(private_root);private_directory(root)
        for name in ('attestor_secret.ed25519.pem','attestor_public.ed25519.pem','frozen_pins.json'):private_keyfile(root/name)
        self.key=serialization.load_pem_private_key(safe_read(root/'attestor_secret.ed25519.pem',4096),password=None)
        if not isinstance(self.key,Ed25519PrivateKey):raise ValueError('Attestor private key must be Ed25519')
        self.public=safe_read(root/'attestor_public.ed25519.pem',4096)
        self.fp=sha(self.public);self.pins=parse(safe_read(root/'frozen_pins.json'))
        if len(self.pins)!=15:raise ValueError('Incomplete frozen original policy')
        self.policy_sha=objhash(self.pins);self.math_socket=Path(math_socket);self.checker_socket=Path(checker_socket);self.math_uid=math_uid;self.checker_uid=checker_uid;self.signer_uid=signer_uid
        self.used=set();self.used_lock=threading.Lock()
        self.lockfd=os.open(root/'.attestor.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        fcntl.flock(self.lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if Path(socket_path).exists():raise ValueError('Preexisting attestor socket')
        super().__init__(str(socket_path),AttestorRequest);os.chmod(socket_path,0o660)
    def prove(self,msg):
        if type(msg)!=dict or set(msg)!={'op','case_id','nonce','policy_sha256'} or msg['op']!='prove':
            raise ValueError('Unexpected attestor request fields')
        case=msg['case_id'];nonce=msg['nonce']
        if type(case)!=str or case not in self.pins or type(nonce)!=str or not HEX64.fullmatch(nonce):
            raise ValueError('Unknown case or malformed nonce')
        if msg['policy_sha256']!=self.policy_sha:raise ValueError('Frozen case policy mismatch')
        with self.used_lock:
            if nonce in self.used:raise ValueError('Repeated attestor challenge')
            self.used.add(nonce)
        reply=math_request(self.math_socket,msg,self.math_uid)
        if type(reply)!=dict or set(reply)!={'ok','result'} or reply['ok'] is not True:
            raise ValueError('No accepted mathematical verification')
        result=reply['result']
        if type(result)!=dict or set(result)!={'version','case_id','nonce','policy_sha256','attestation'} or \
          result['version']!=1 or result['case_id']!=case or result['nonce']!=nonce or result['policy_sha256']!=self.policy_sha:
            raise ValueError('Mathematical result did not bind case/nonce/policy')
        verify_attestation(result['attestation'],case,self.pins[case])
        # Checker owns separate sealed sources and runs a fresh MPFR certificate
        # verification, not a comparison against worker-supplied success flags.
        checked=math_request(self.checker_socket,{'op':'check','case_id':case,
             'nonce':nonce,'policy_sha256':self.policy_sha,
             'reported_attestation':result['attestation']},self.checker_uid)
        if type(checked)!=dict or set(checked)!={'ok','receipt'} or checked['ok'] is not True:
            raise ValueError('Independent checker unavailable or refused proof')
        receipt=verify_checker_receipt(checked['receipt'],result['attestation'],case,nonce,self.policy_sha)
        body={'version':1,'nonce':nonce,'case_id':case,'policy_sha256':self.policy_sha,
            'attestor_fingerprint_sha256':self.fp,'attestation':result['attestation'], 'checker_receipt':receipt}
        return {'body':body,'signature':base64.b64encode(self.key.sign(V_DOMAIN+canonical(body))).decode('ascii')}

def provision_attestor(root,pins):
    root=Path(root)
    if root.exists():raise FileExistsError('Refuse overwrite of attestor identity')
    root.mkdir(mode=0o700)
    key=Ed25519PrivateKey.generate()
    priv=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    pub=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    for name,data in [('attestor_secret.ed25519.pem',priv),('attestor_public.ed25519.pem',pub),('frozen_pins.json',canonical(pins)+b'\n')]:
        fd=os.open(root/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    sync_dir(root)
    return {'attestor_fingerprint_sha256':sha(pub),'policy_sha256':objhash(pins)}

def main():
    p=argparse.ArgumentParser()
    for name in ('socket','private','math-socket','checker-socket'):p.add_argument('--'+name,required=True)
    p.add_argument('--math-uid',required=True,type=int);p.add_argument('--checker-uid',required=True,type=int);p.add_argument('--signer-uid',required=True,type=int)
    a=p.parse_args();s=AttestorDaemon(a.socket,private_root=a.private,math_socket=a.math_socket,checker_socket=a.checker_socket,math_uid=a.math_uid,checker_uid=a.checker_uid,signer_uid=a.signer_uid)
    try:s.serve_forever(poll_interval=.2)
    finally:s.server_close()
if __name__=='__main__':main()
