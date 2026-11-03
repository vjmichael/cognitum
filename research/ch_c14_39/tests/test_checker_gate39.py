"""CH39 protocol adversarial tests; mocks here do NOT substitute for live CH23 MPFR replay."""
import copy,concurrent.futures,sys
from pathlib import Path
import pytest
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import checker39,attestor39
from checker39 import IndependentChecker
from attestor39 import AttestorDaemon,provision_attestor
from protocol39 import objhash,verify_ticket,verify_checker_receipt,parse,canonical
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

CASE='case00';NONCE='a'*64

def pins():return {f'case{i:02d}':{'original_head_sha256':str(i%10)*64,
          'checkpoint_sha256':str((i+1)%10)*64,'nodes':127} for i in range(15)}

def att(p,case=CASE):return {'case_id':case,'binding_sha256':'a'*64,
  'original_head_sha256':p[case]['original_head_sha256'],
  'checkpoint_sha256':p[case]['checkpoint_sha256'],'archive_sha256':'b'*64,
  'nodes':127,'archive_epochs':2,'mpfr_replayed_frames':6,
  'proof_replayed':True,'scientific_release':'NO_GO','verified_source':'original_CH23_independent_MPFR_224'}

def msg(p,nonce=NONCE):return {'op':'check','case_id':CASE,'nonce':nonce,
    'policy_sha256':objhash(p),'reported_attestation':att(p)}

def proof_msg(p):return {'op':'prove','case_id':CASE,'nonce':NONCE,'policy_sha256':objhash(p)}

@pytest.fixture
def checker(tmp_path,monkeypatch):
    p=pins();private=tmp_path/'private';private.mkdir(mode=0o700)
    (private/'frozen_pins.json').write_bytes(canonical(p)+b'\n');(private/'frozen_pins.json').chmod(0o600)
    service=IndependentChecker(tmp_path/'checker.sock',private_root=private,source_root=tmp_path,
       proof_root=tmp_path,attestor_uid=1003,math_uid=1002,workers=1)
    real=service.pool
    class Pool:
        def submit(self,*args):
            result=concurrent.futures.Future();result.set_result(att(p));return result
        def shutdown(self,**kw):pass
    real.shutdown(wait=True,cancel_futures=True);service.pool=Pool()
    try:yield service,p
    finally:service.server_close()

@pytest.fixture
def authority(tmp_path):
    p=pins();priv=tmp_path/'attestor';provision_attestor(priv,p)
    srv=AttestorDaemon(tmp_path/'attestor.sock',private_root=priv,math_socket=tmp_path/'math.sock',
                        checker_socket=tmp_path/'checker.sock',math_uid=1002,checker_uid=1004,signer_uid=65534)
    try:yield srv,p
    finally:srv.server_close()

def test_fresh_checker_reports_independent_match(checker):
    c,p=checker
    receipt=c.check(msg(p))
    assert receipt['checker_attestation_sha256']==objhash(att(p))
    verify_checker_receipt(receipt,att(p),CASE,NONCE,objhash(p))

def test_unchecked_false_math_success_does_not_pass(checker):
    c,p=checker
    forged=msg(p);forged['reported_attestation']['archive_sha256']='c'*64
    with pytest.raises(ValueError,match='differs'):c.check(forged)

def test_incorrect_math_binding_rejected(checker):
    c,p=checker
    forged=msg(p);forged['reported_attestation']['binding_sha256']='c'*64
    with pytest.raises(ValueError,match='differs'):c.check(forged)

def test_bad_case_pin_rejected(checker):
    c,p=checker;forged=msg(p);forged['reported_attestation']['original_head_sha256']='f'*64
    with pytest.raises(ValueError):c.check(forged)

@pytest.mark.parametrize('field,new', [('nonce','bad'),('policy_sha256','f'*64),('op','prove'),('case_id','unlisted')])
def test_checker_rejects_wrong_scope(checker,field,new):
    c,p=checker;forged=msg(p);forged[field]=new
    with pytest.raises(ValueError):c.check(forged)

def test_checker_rejects_replayed_nonce(checker):
    c,p=checker;c.check(msg(p))
    with pytest.raises(ValueError,match='replay'):c.check(msg(p))

def test_checker_error_never_allows_signed_ticket(authority,monkeypatch):
    s,p=authority
    def route(path,body,uid,timeout=900):
        if uid==1002:
            return {'ok':True,'result':{'version':1,'nonce':NONCE,'case_id':CASE,
                'policy_sha256':objhash(p),'attestation':att(p)}}
        return {'ok':False,'error':'ValueError'}
    monkeypatch.setattr(attestor39,'math_request',route)
    with pytest.raises(ValueError,match='Independent checker'):s.prove(proof_msg(p))

def test_checker_absent_refuses_signature(authority,monkeypatch):
    s,p=authority
    def route(path,body,uid,timeout=900):
        if uid==1002:
            return {'ok':True,'result':{'version':1,'nonce':NONCE,'case_id':CASE,
                'policy_sha256':objhash(p),'attestation':att(p)}}
        raise FileNotFoundError('Checker offline')
    monkeypatch.setattr(attestor39,'math_request',route)
    with pytest.raises(FileNotFoundError):s.prove(proof_msg(p))

def test_valid_checker_attestor_dual_binding(authority,checker,monkeypatch):
    s,p=authority;c,_=checker
    def route(path,body,uid,timeout=900):
        if uid==1002:
            return {'ok':True,'result':{'version':1,'nonce':NONCE,'case_id':CASE,
                'policy_sha256':objhash(p),'attestation':att(p)}}
        return {'ok':True,'receipt':c.check(body)}
    monkeypatch.setattr(attestor39,'math_request',route)
    ticket=s.prove(proof_msg(p))
    verify_ticket(ticket,s.public,s.fp,objhash(p),CASE,NONCE,p)

def test_forged_checker_digest_rejected(authority,monkeypatch):
    s,p=authority
    def route(path,body,uid,timeout=900):
        if uid==1002:return {'ok':True,'result':{'version':1,'nonce':NONCE,'case_id':CASE,
                'policy_sha256':objhash(p),'attestation':att(p)}}
        return {'ok':True,'receipt':{'version':1,'case_id':CASE,'nonce':NONCE,'policy_sha256':objhash(p),
              'worker_attestation_sha256':objhash(att(p)),'checker_attestation_sha256':'f'*64,
              'checker_result':'INDEPENDENT_REPLAY_ACCEPTED','checker_scope':'FROZEN_CH23_127_NODES_6_FRAMES_MPFR_224'}}
    monkeypatch.setattr(attestor39,'math_request',route)
    with pytest.raises(ValueError):s.prove(proof_msg(p))

@pytest.mark.parametrize('field,replacement', [('checker_result','PASS'),('checker_scope','WRONG'),('nonce','b'*64),('case_id','case01'),('policy_sha256','c'*64)])
def test_checker_receipt_rejects_scope_forgery(checker,field,replacement):
    c,p=checker;rc=c.check(msg(p));rc[field]=replacement
    with pytest.raises(ValueError):verify_checker_receipt(rc,att(p),CASE,NONCE,objhash(p))

def test_trusted_failure_is_fail_closed_even_with_worker_success(checker):
    c,p=checker
    class BadPool:
        def shutdown(self,**kw):pass
        def submit(self,*args):
            f=concurrent.futures.Future();f.set_exception(ValueError('MPFR bound falsified'));return f
    c.pool=BadPool()
    with pytest.raises(ValueError,match='MPFR'):c.check(msg(p))

@pytest.mark.parametrize('change', [lambda a:a.update({'proof_replayed':False}),
        lambda a:a.update({'nodes':126}),lambda a:a.update({'scientific_release':'GO'})])
def test_false_math_claim_rejected_before_checker(checker,change):
    c,p=checker;m=msg(p);change(m['reported_attestation'])
    with pytest.raises(ValueError):c.check(m)
