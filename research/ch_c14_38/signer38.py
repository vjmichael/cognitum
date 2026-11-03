"""Linux signer under independent UID. NO access to MPFR code or proof files.

A verified, fresh, attestor-UID-signed MPFR ticket must be validated before
this account can sign/publish a new independently scoped witness revision.
"""
from __future__ import annotations
import argparse, fcntl, json, os, secrets, socket, socketserver, threading
from pathlib import Path
from protocol38 import (canonical, parse, peersock, request,verify_ticket)
from trust38 import DualSignerStore

class SignerRequest(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            pid,uid,gid=peersock(self.request)
            if uid!=self.server.writer_uid:raise PermissionError('Signer admits only writer UID')
            raw=self.rfile.readline(4097)
            if len(raw)>4096:raise ValueError('Writer request oversized')
            msg=parse(raw,4096)
            res=self.server.handle_message(msg)
            self.wfile.write(canonical({'ok':True,'result':res})+b'\n')
        except Exception as err:
            self.wfile.write(canonical({'ok':False,'error':type(err).__name__,'detail':str(err)[:140]})+b'\n')

class DualSigner(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
    daemon_threads=True
    allow_reuse_address=False
    def __init__(self,socket_path,*,store,attestor_socket,writer_uid,attestor_uid):
        if os.geteuid() in (writer_uid,attestor_uid):raise PermissionError('Signer UID must be distinct')
        self.store=DualSignerStore(store)
        self.attestor_socket=Path(attestor_socket);self.writer_uid=writer_uid
        self.attestor_uid=attestor_uid;self.commit=threading.Lock()
        self.lock_fd=os.open(self.store.root/'.signer.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        fcntl.flock(self.lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if Path(socket_path).exists():raise ValueError('Refuse preexisting signer socket')
        super().__init__(str(socket_path),SignerRequest)
        os.chmod(socket_path,0o660)
    def handle_message(self,msg):
        if type(msg)!=dict or set(msg)!={'op','case_id'} or msg['op']!='verify':
            raise ValueError('Writer may only request proof of a frozen case')
        case=msg['case_id']
        if type(case)!=str or case not in self.store.pins:raise ValueError('Unknown original case')
        # Two-stage duplicate checks keep publication serialized while distinct
        # attestor UID workers can perform the expensive MPFR replay in parallel.
        with self.commit:
            before=self.store.audit()
            if case in before['cases']:raise ValueError('Original case already signed')
        nonce=secrets.token_hex(32)
        reply=request(self.attestor_socket,{'op':'prove','case_id':case,
                            'nonce':nonce,'policy_sha256':self.store.policy_sha},timeout=900)
        if set(reply)!={'ok','ticket'} or reply['ok'] is not True:
            raise ValueError('Attestor denied mathematical proof')
        ticket=reply['ticket']
        verify_ticket(ticket,self.store.attestor_public,self.store.vf,
                      self.store.policy_sha,case,nonce,self.store.pins)
        with self.commit:
            current=self.store.audit()
            if case in current['cases']:raise ValueError('Concurrent duplicate request refused')
            return {'status':'SIGNED_AFTER_SEPARATE_UID_MPFR','case_id':case,
                    'scientific_release':'NO_GO',**self.store.publish(case,ticket)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--socket',required=True);p.add_argument('--store',required=True)
    p.add_argument('--attestor-socket',required=True)
    p.add_argument('--writer-uid',type=int,required=True);p.add_argument('--attestor-uid',type=int,required=True)
    a=p.parse_args()
    s=DualSigner(a.socket,store=a.store,attestor_socket=a.attestor_socket,
                 writer_uid=a.writer_uid,attestor_uid=a.attestor_uid)
    try:s.serve_forever(poll_interval=.2)
    finally:s.server_close()
if __name__=='__main__':main()
