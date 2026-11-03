"""CH40G UID1003 independent research attestor, adapted from CH39 original.
Requires UID1002 actual MPFR replay, UID1004 actual CH39 + independent CH40F
replays, frozen cap trace pins and challenge binding prior to Ed25519 signature.
"""
from __future__ import annotations
import argparse,base64
from attestor39 import AttestorDaemon, math_request
from protocol39 import HEX64,V_DOMAIN,canonical,verify_attestation,verify_checker_receipt
from caps_policy40g import validate_caps

class CapsAttestor(AttestorDaemon):
    def prove(self,msg):
        if type(msg)!=dict or set(msg)!={'op','case_id','nonce','policy_sha256'} or msg['op']!='prove':
            raise ValueError('Unexpected attestor request fields')
        case,nonce=msg['case_id'],msg['nonce']
        if type(case)!=str or case not in self.pins or type(nonce)!=str or not HEX64.fullmatch(nonce):
            raise ValueError('Unknown case or malformed nonce')
        if msg['policy_sha256']!=self.policy_sha:raise ValueError('Frozen source policy mismatch')
        with self.used_lock:
            if nonce in self.used:raise ValueError('Repeated attestor challenge')
            self.used.add(nonce)
        worker=math_request(self.math_socket,msg,self.math_uid)
        if type(worker)!=dict or set(worker)!={'ok','result'} or worker['ok'] is not True:
            raise ValueError('Worker did not produce accepted original MPFR result')
        w=worker['result']
        if type(w)!=dict or set(w)!={'version','case_id','nonce','policy_sha256','attestation'} or \
           w['version']!=1 or w['case_id']!=case or w['nonce']!=nonce or w['policy_sha256']!=self.policy_sha:
            raise ValueError('Untrusted worker result not challenge-bound')
        verify_attestation(w['attestation'],case,self.pins[case])
        # SO_PEERCRED on accepted AF_UNIX endpoint must be UID1004, not a
        # claimed UID supplied in the receipt itself.
        checked=math_request(self.checker_socket,{'op':'check','case_id':case,'nonce':nonce,
            'policy_sha256':self.policy_sha,'reported_attestation':w['attestation']},self.checker_uid,timeout=900)
        if type(checked)!=dict or set(checked)!={'ok','receipt'} or checked['ok'] is not True:
            raise ValueError('Independent checker absent/failed or interrupted')
        contents=checked['receipt']
        if type(contents)!=dict or set(contents)!={'ch39_receipt','cap_receipt'}:
            raise ValueError('Missing independent mathematical receipts')
        legacy=verify_checker_receipt(contents['ch39_receipt'],w['attestation'],case,nonce,self.policy_sha)
        caps=validate_caps(contents['cap_receipt'],case,nonce,self.policy_sha,self.pins[case])
        body={'version':1,'nonce':nonce,'case_id':case,'policy_sha256':self.policy_sha,
              'attestor_fingerprint_sha256':self.fp,'attestation':w['attestation'],
              'checker_receipt':legacy,'caps_receipt':caps}
        return {'body':body,'signature':base64.b64encode(self.key.sign(V_DOMAIN+canonical(body))).decode('ascii')}

def main():
    p=argparse.ArgumentParser()
    for n in ('socket','private','math-socket','checker-socket'):p.add_argument('--'+n,required=True)
    for n in ('math-uid','checker-uid','signer-uid'):p.add_argument('--'+n,type=int,required=True)
    a=p.parse_args();s=CapsAttestor(a.socket,private_root=a.private,math_socket=a.math_socket,
       checker_socket=a.checker_socket,math_uid=a.math_uid,checker_uid=a.checker_uid,signer_uid=a.signer_uid)
    try:s.serve_forever(poll_interval=.2)
    finally:s.server_close()
if __name__=='__main__':main()
