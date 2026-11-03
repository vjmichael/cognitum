"""ONLY FOR ADVERSARIAL ACCEPTANCE: forged result using public pinned schema.

This is not a mathematical verifier. It is a substitute attacker for UID1002.
"""
import argparse,socketserver
from pathlib import Path
from protocol39 import parse,canonical,objhash,peersock

class H(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            _,uid,_=peersock(self.request)
            if uid!=self.server.attestor_uid:raise PermissionError('Not the attestor')
            m=parse(self.rfile.readline(4097),4096);case=m['case_id'];nonce=m['nonce']
            pin=self.server.pins[case];assert m['policy_sha256']==objhash(self.server.pins)
            fake={'case_id':case,'binding_sha256':'a'*64,
                 'original_head_sha256':pin['original_head_sha256'],
                 'checkpoint_sha256':pin['checkpoint_sha256'],
                 # A falsified but syntactically correct arithmetic/proof digest.
                 'archive_sha256':'f'*64,'nodes':127,'archive_epochs':2,
                 'mpfr_replayed_frames':6,'proof_replayed':True,
                 'scientific_release':'NO_GO','verified_source':'original_CH23_independent_MPFR_224'}
            reply={'ok':True,'result':{'version':1,'case_id':case,'nonce':nonce,
                   'policy_sha256':objhash(self.server.pins),'attestation':fake}}
            self.wfile.write(canonical(reply)+b'\n')
        except Exception as exc:self.wfile.write(canonical({'ok':False,'error':type(exc).__name__})+b'\n')
class Fake(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
    daemon_threads=True
    def __init__(self,sock,pins,attestor_uid):
        self.pins=parse(Path(pins).read_bytes());self.attestor_uid=attestor_uid
        super().__init__(str(sock),H);Path(sock).chmod(0o660)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--socket',required=True);p.add_argument('--pins',required=True)
    p.add_argument('--attestor-uid',type=int,required=True);a=p.parse_args()
    s=Fake(a.socket,a.pins,a.attestor_uid)
    try:s.serve_forever(.2)
    finally:s.server_close()
