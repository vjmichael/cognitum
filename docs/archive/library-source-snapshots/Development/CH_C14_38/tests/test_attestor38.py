"""CH38 attestor rejects malformed/mismatched claims without accessing MPFR source.

These protocol fakes are NOT substitutes for the original CH23 mathematical runs.
"""
import copy,errno,json,os,sys
from pathlib import Path
import pytest
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import attestor38
from attestor38 import AttestorDaemon,provision_attestor,math_request
from protocol38 import canonical,objhash,sha,verify_ticket
from test_protocol38 import pins,att

@pytest.fixture
def authority(tmp_path):
    p=pins();private=tmp_path/'private';provision_attestor(private,p)
    service=AttestorDaemon(tmp_path/'attestor.sock',private_root=private,math_socket=tmp_path/'no-math.sock',
                          math_uid=1002,signer_uid=65534)
    try:yield service,private,p
    finally:service.server_close()

def msg(p,case='case00',nonce='a'*64):
    return {'op':'prove','case_id':case,'nonce':nonce,'policy_sha256':objhash(p)}

def answer(p,case='case00',nonce='a'*64):
    return {'ok':True,'result':{'version':1,'case_id':case,'nonce':nonce,'policy_sha256':objhash(p),
                              'attestation':att(case,p[case])}}

def test_valid_fake_math_shape_attestation_is_signed_but_not_math_proof(authority,monkeypatch):
    s,store,p=authority
    monkeypatch.setattr(attestor38,'math_request',lambda *a,**kw: answer(p))
    ticket=s.prove(msg(p))
    verify_ticket(ticket,s.public,s.fp,objhash(p),'case00','a'*64,p)
    assert ticket['body']['attestor_fingerprint_sha256']==sha(s.public)
    # This is deliberately a protocol-only stub. A compromised math UID could
    # forge the identical shape. CH38 key isolation is not honest-computation proof.

def test_math_service_absent_no_ticket(authority):
    s,_,p=authority
    with pytest.raises((FileNotFoundError,OSError)):s.prove(msg(p))

def test_attestor_key_permissions_enforced(authority):
    s,private,p=authority;s.server_close()
    (private/'attestor_secret.ed25519.pem').chmod(0o644)
    with pytest.raises(PermissionError):AttestorDaemon(private.parent/'new.sock',private_root=private,
                                                       math_socket=private.parent/'x',math_uid=1002,signer_uid=65534)

@pytest.mark.parametrize('modify',[
    lambda x: x.update({'nonce':'b'*64}),
    lambda x: x.update({'case_id':'case01'}),
    lambda x: x.update({'policy_sha256':'0'*64}),
    lambda x: x.update({'version':99}),
    lambda x: x.update({'extra':'bad'}),
])
def test_rejects_math_result_wrong_binding(authority,monkeypatch,modify):
    s,_,p=authority
    data=answer(p);modify(data['result'])
    monkeypatch.setattr(attestor38,'math_request',lambda *a,**kw:data)
    with pytest.raises(ValueError):s.prove(msg(p))

def test_rejects_math_false_success(authority,monkeypatch):
    s,_,p=authority
    data=answer(p);data['result']['attestation']['proof_replayed']=False
    monkeypatch.setattr(attestor38,'math_request',lambda *a,**kw:data)
    with pytest.raises(ValueError):s.prove(msg(p))

def test_rejects_math_changed_frozen_head(authority,monkeypatch):
    s,_,p=authority
    data=answer(p);data['result']['attestation']['original_head_sha256']='9'*64
    monkeypatch.setattr(attestor38,'math_request',lambda *a,**kw:data)
    with pytest.raises(ValueError):s.prove(msg(p))

def test_rejects_math_missing_response_fields(authority,monkeypatch):
    s,_,p=authority
    monkeypatch.setattr(attestor38,'math_request',lambda *a,**kw:{'ok':False,'error':'PermissionError'})
    with pytest.raises(ValueError):s.prove(msg(p))

def test_duplicate_challenge_refused_before_math_call(authority,monkeypatch):
    s,_,p=authority
    calls=[]
    def returned(*args,**kw):calls.append(1);return answer(p)
    monkeypatch.setattr(attestor38,'math_request',returned)
    s.prove(msg(p))
    with pytest.raises(ValueError,match='Repeated'):s.prove(msg(p))
    assert len(calls)==1

def test_attestor_cannot_accept_writer_supplied_ticket(authority):
    s,_,p=authority
    bad={**msg(p),'attestation':att('case00',p['case00'])}
    with pytest.raises(ValueError):s.prove(bad)

def test_socket_peer_uid_must_match_math_uid(tmp_path,monkeypatch):
    # A falsified endpoint can be reached only if path permissions fail. The
    # attestor additionally validates kernel peer UID before sending any case.
    import socket
    path=str(tmp_path/'listener.sock')
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(path);server.listen()
    try:
        with pytest.raises(PermissionError,match='Untrusted mathematical-service'):
            math_request(path,{'op':'prove'},uid=1002,timeout=1)
    finally:server.close()