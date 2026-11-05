"""Disposable hostile UID1002 mathematical service for CH40G real-OS attack tests.
Attacker reports a fully plausible CH39 result based on already-public signed
historical evidence. Nothing generated here is certified mathematics.
"""
from __future__ import annotations
import argparse,json,os,socketserver,base64
from protocol39 import parse,canonical,peersock
class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            _,uid,_=peersock(self.request)
            if uid!=self.server.attestor_uid:raise PermissionError('Wrong caller UID')
            req=parse(self.rfile.readline(4097),4096)
            if set(req)!={'op','case_id','nonce','policy_sha256'} or req['op']!='prove':raise ValueError('request')
            att=dict(self.server.attestation)
            if req['case_id']!=att['case_id']:raise ValueError('unknown case')
            if self.server.corrupt:att['archive_sha256']='0'*64
            r={'ok':True,'result':{'version':1,'case_id':req['case_id'],'nonce':req['nonce'],
                        'policy_sha256':req['policy_sha256'],'attestation':att}}
            self.wfile.write(canonical(r)+b'\n')
        except Exception as e:self.wfile.write(canonical({'ok':False,'error':type(e).__name__})+b'\n')
class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
    daemon_threads=True;allow_reuse_address=False
    def __init__(self,path,attestation,attestor_uid,corrupt):
        self.attestation=attestation;self.attestor_uid=attestor_uid;self.corrupt=corrupt
        super().__init__(path,Handler);os.chmod(path,0o660)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--socket',required=True);p.add_argument('--attestation',required=True)
    p.add_argument('--attestor-uid',type=int,required=True);p.add_argument('--corrupt',action='store_true');a=p.parse_args()
    srv=Server(a.socket,json.load(open(a.attestation)),a.attestor_uid,a.corrupt);srv.serve_forever(poll_interval=.2)