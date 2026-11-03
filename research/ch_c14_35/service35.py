"""CH35 Linux AF_UNIX signer service. Run under a separate, unprivileged UID.

The write-capable journal owner has no API to submit attestations, paths,
proof hashes, signatures or signer keys. Only a frozen case id can be sent.
"""
from __future__ import annotations
import argparse, fcntl, json, os, socket, socketserver, stat, struct, sys, traceback
from pathlib import Path
from trust35 import (GENESIS, WitnessStore, atomic, canonical, nofollow_read,
                     pubkey_fingerprint, verify_chain, witness_original_ch33)

class WitnessService(socketserver.UnixStreamServer):
    allow_reuse_address=False
    def __init__(self,socket_path, *, store, source_root, journals_root, allowed_uid=None):
        self.store=WitnessStore(store)
        self.source_root=Path(source_root);self.journals_root=Path(journals_root)
        self.pins=json.loads(nofollow_read(self.store.root/'frozen_pins.json',65536))
        self.allowed_uid=allowed_uid
        self.seized=os.open(self.store.root/'.server.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        fcntl.flock(self.seized,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.public=nofollow_read(self.store.root/'public.ed25519.pem',4096)
        self.fingerprint=pubkey_fingerprint(self.public)
        self.pin_path=self.store.root/'trusted_tip.json'
        if Path(socket_path).exists():raise ValueError('Refuse to unlink/replace an existing IPC socket')
        super().__init__(str(socket_path),Request)
        os.chmod(socket_path,0o666)
    def trusted_tip(self):
        obj=json.loads(nofollow_read(self.pin_path,1024))
        if set(obj)!={'tip','fingerprint'} or obj['fingerprint']!=self.fingerprint:
            raise ValueError('Protected authority tip damaged')
        return obj['tip']
    def handle_message(self,msg,uid):
        if self.allowed_uid is not None and uid!=self.allowed_uid:
            raise PermissionError('Unpermitted client OS user')
        if type(msg)!=dict or set(msg)!= {'op','case_id'} or msg['op']!='verify':
            raise ValueError('Only independent verification of a frozen case is permitted')
        case=msg['case_id']
        if type(case)!=str or case not in self.pins:
            raise ValueError('Unknown case; authority never accepts caller-supplied proof digests')
        tip=self.trusted_tip()
        current=verify_chain(self.store.root,self.public,expected_fingerprint=self.fingerprint,expected_tip=tip)
        if case in current['cases']:raise ValueError('Original frozen case already signed')
        att=witness_original_ch33(case,self.source_root,self.journals_root,self.pins)
        result=self.store.publish(att,expected_tip=tip)
        # Publication is not finished until the authority-controlled pin is
        # durably advanced. If interrupted, future signing refuses rollback.
        atomic(self.store.root,'trusted_tip.json',canonical({'tip':result['tip'],
               'fingerprint':self.fingerprint})+b'\n',prefix='tip')
        return {'status':'SIGNED_AFTER_INDEPENDENT_MPFR_REPLAY','tip_sha256':result['tip'],
                'record':result['record'],'public_key_fingerprint_sha256':self.fingerprint,
                'scientific_release':'NO_GO'}

class Request(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            credentials=self.request.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize('3i'))
            pid,uid,gid=struct.unpack('3i',credentials)
            raw=self.rfile.readline(4097)
            if len(raw)>4096 or not raw.endswith(b'\n'):raise ValueError('Request too large or not terminated')
            def unique(kv):
                d={}
                for k,v in kv:
                    if k in d:raise ValueError('Duplicate JSON request key')
                    d[k]=v
                return d
            msg=json.loads(raw,object_pairs_hook=unique)
            answer=self.server.handle_message(msg,uid)
            self.wfile.write(canonical({'ok':True,'result':answer})+b'\n')
        except (Exception,BaseException) as e:
            # Server errors fail closed without publishing private details.
            self.wfile.write(canonical({'ok':False,'error':type(e).__name__,
                'detail':str(e)[:180]})+b'\n')


def client(socket_path,case):
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    try:
        s.settimeout(900);s.connect(str(socket_path))
        s.sendall(canonical({'op':'verify','case_id':case})+b'\n')
        raw=b''
        while not raw.endswith(b'\n'):
            chunk=s.recv(65536)
            if not chunk:raise ValueError('Witness closed without response')
            raw+=chunk
            if len(raw)>65536:raise ValueError('Oversized witness response')
        return json.loads(raw)
    finally:s.close()


def provision(root,protected_source,*,pins):
    """Operator-only one-time setup; caller must protect source before service."""
    out=WitnessStore.provision(root)
    root=Path(root)
    for name,obj in [('trusted_tip.json',{'tip':GENESIS,'fingerprint':out['fingerprint_sha256']}),
                     ('frozen_pins.json',pins)]:
        fd=os.open(root/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(canonical(obj)+b'\n');f.flush();os.fsync(f.fileno())
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('serve')
    for field in ('socket','store','source','journals'):s.add_argument('--'+field,required=True)
    s.add_argument('--allowed-uid',type=int,default=None)
    s=sub.add_parser('request');s.add_argument('--socket',required=True);s.add_argument('--case',required=True)
    a=p.parse_args()
    if a.cmd=='request':print(json.dumps(client(a.socket,a.case),sort_keys=True))
    else:
        srv=WitnessService(a.socket,store=a.store,source_root=a.source,
                           journals_root=a.journals,allowed_uid=a.allowed_uid)
        try:srv.serve_forever(poll_interval=0.2)
        finally:srv.server_close()
