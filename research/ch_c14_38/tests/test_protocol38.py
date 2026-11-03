"""Adversarial CH37 signed-wire contract and ledger safety tests (no MPFR)."""
import base64, copy, json, os, sys, tempfile
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D))
from protocol38 import (ZERO,V_DOMAIN,canonical,objhash,sha,parse,verify_ticket,verify_attestation)
from trust38 import (DualSignerStore,audit_chain,provision_signer)

def pkpair():
    key=Ed25519PrivateKey.generate()
    return key,key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)

def pins():
    return {f'case{i:02d}':{'original_head_sha256':sha(f'head{i}'.encode()),
                              'checkpoint_sha256':sha(f'cp{i}'.encode()),
                              'checkpoint_file_sha256':sha(f'bytes{i}'.encode()),
                              'nodes':127} for i in range(15)}

def att(case,pin):
    return {'case_id':case,'original_head_sha256':pin['original_head_sha256'],
            'checkpoint_sha256':pin['checkpoint_sha256'],'binding_sha256':sha(b'bind'),
            'archive_sha256':sha(b'archive'),'nodes':127,'archive_epochs':2,
            'mpfr_replayed_frames':6,'proof_replayed':True,'scientific_release':'NO_GO',
            'verified_source':'original_CH23_independent_MPFR_224'}

def ticket(key,pins,case='case00',nonce='a'*64):
    ver_pub=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    body={'version':1,'case_id':case,'nonce':nonce,'policy_sha256':objhash(pins),
          'attestor_fingerprint_sha256':sha(ver_pub),'attestation':att(case,pins[case])}
    return {'body':body,'signature':base64.b64encode(key.sign(V_DOMAIN+canonical(body))).decode()}

@pytest.fixture
def initialized():
    key,pub=pkpair();p=pins();case='case00'
    with tempfile.TemporaryDirectory() as t:
        root=Path(t)/'signer';provision_signer(root,pub,p)
        store=DualSignerStore(root)
        yield key,pub,p,store,root

def test_valid_two_signatures_and_contiguous_ledger(initialized):
    key,pub,p,store,root=initialized
    first=ticket(key,p,'case00');a=store.publish('case00',first)
    second=ticket(key,p,'case01',nonce='b'*64);b=store.publish('case01',second)
    result=store.audit()
    assert result['length']==2 and result['cases']==['case00','case01']
    assert result['verified_signer_signatures']==2 and result['verified_attestor_tickets']==2
    assert b['tip_sha256']!=a['tip_sha256']

def test_replay_and_wrong_nonce_fail(initialized):
    key,pub,p,store,root=initialized
    proof=ticket(key,p)
    with pytest.raises(ValueError):verify_ticket(proof,pub,sha(pub),objhash(p),'case00','b'*64,p)
    store.publish('case00',proof)
    with pytest.raises(ValueError,match='Previously signed'):store.publish('case00',proof)

def test_two_different_cases_with_reused_attestor_nonce_refuse(initialized):
    key,pub,p,store,root=initialized
    store.publish('case00',ticket(key,p,'case00'))
    with pytest.raises(ValueError,match='Duplicate attestor nonce'):store.publish('case01',ticket(key,p,'case01'))

def test_fake_writer_signed_ticket_refused(initialized):
    key,pub,p,store,root=initialized
    bad=copy.deepcopy(ticket(key,p));bad['body']['attestation']['proof_replayed']=False
    with pytest.raises(ValueError):store.publish('case00',bad)
    forged,other=pkpair()
    fake=ticket(forged,p)
    with pytest.raises(ValueError):store.publish('case00',fake)

def test_signer_cannot_certify_global_optimality(initialized):
    key,pub,p,store,root=initialized
    fake=ticket(key,p);fake['body']['attestation']['scientific_release']='GO'
    fake['signature']=base64.b64encode(key.sign(V_DOMAIN+canonical(fake['body']))).decode()
    with pytest.raises(ValueError):store.publish('case00',fake)

def test_wrong_policy_or_different_checkpoint_refused(initialized):
    key,pub,p,store,root=initialized
    proof=ticket(key,p)
    proof['body']['attestation']['checkpoint_sha256']=sha(b'other')
    proof['signature']=base64.b64encode(key.sign(V_DOMAIN+canonical(proof['body']))).decode()
    with pytest.raises(ValueError):store.publish('case00',proof)
    proof=ticket(key,p)
    proof['body']['policy_sha256']=sha(b'other')
    proof['signature']=base64.b64encode(key.sign(V_DOMAIN+canonical(proof['body']))).decode()
    with pytest.raises(ValueError):store.publish('case00',proof)

def test_rollback_anchor_detected(initialized):
    key,pub,p,store,root=initialized
    a=store.publish('case00',ticket(key,p))
    b=store.publish('case01',ticket(key,p,'case01',nonce='b'*64))
    (root/'HEAD').write_bytes(canonical(a['record'])+b'\n')
    with pytest.raises(ValueError,match='rollback'):store.audit()

def test_bogus_attestation_or_orphan_fail_closed(initialized):
    key,pub,p,store,root=initialized
    store.publish('case00',ticket(key,p))
    (root/'revisions'/('00000001_'+sha(b'fake')+'.json')).write_text('bad\n')
    with pytest.raises(ValueError,match='Orphan'):store.publish('case01',ticket(key,p,'case01',nonce='b'*64))

def test_signed_record_tamper_refused(initialized):
    key,pub,p,store,root=initialized
    item=store.publish('case00',ticket(key,p))
    broken=copy.deepcopy(item['record']);broken['body']['case_id']='case01'
    (root/'HEAD').write_bytes(canonical(broken)+b'\n')
    with pytest.raises(ValueError):store.audit()

def test_attestor_public_key_substitution_refused(initialized):
    key,pub,p,store,root=initialized
    store.publish('case00',ticket(key,p))
    other=pkpair()[1]
    with pytest.raises(ValueError):audit_chain(root,store.public,other,
        signer_fingerprint=store.sf,attestor_fingerprint=store.vf,
        expected_tip=store.tip(),pins=p)

def test_noncanonical_and_duplicate_json_refused():
    for raw in [b'{"a":1,"a":2}\n',b'{"z":1,"a":2}\n',b'{"a":NaN}\n',b'{"a":1} garbage\n']:
        with pytest.raises((ValueError,json.JSONDecodeError)):parse(raw)

def test_partial_record_before_head_fails_closed(initialized,monkeypatch):
    import trust38
    key,pub,p,store,root=initialized
    original=trust38.atomic
    def fault(directory,name,data):
        if name=='HEAD':raise OSError(28,'Injected ENOSPC before HEAD')
        return original(directory,name,data)
    monkeypatch.setattr(trust38,'atomic',fault)
    with pytest.raises(OSError):store.publish('case00',ticket(key,p))
    assert store.audit()['length']==0
    with pytest.raises(ValueError,match='Orphan'):store.publish('case00',ticket(key,p))

def test_signed_head_before_tip_requires_manual_reconciliation(initialized,monkeypatch):
    import trust38
    key,pub,p,store,root=initialized
    original=trust38.atomic
    def fault(directory,name,data):
        if name=='trusted_tip.json':raise OSError(5,'Injected EIO before protected-tip update')
        return original(directory,name,data)
    monkeypatch.setattr(trust38,'atomic',fault)
    with pytest.raises(OSError):store.publish('case00',ticket(key,p))
    with pytest.raises(ValueError,match='rollback'):store.audit()
    with pytest.raises(ValueError):store.publish('case01',ticket(key,p,'case01',nonce='b'*64))

def test_relaxed_signing_key_mode_rejected(initialized):
    key,pub,p,store,root=initialized
    secret=root/'secret.ed25519.pem';secret.chmod(0o644)
    with pytest.raises(PermissionError):DualSignerStore(root)

def test_signer_restart_reloads_dual_signature_policy(initialized):
    key,pub,p,store,root=initialized
    first=store.publish('case00',ticket(key,p,'case00'))
    recovered=DualSignerStore(root)
    assert recovered.sf==store.sf and recovered.vf==store.vf
    assert recovered.audit()['cases']==['case00']
    next_result=recovered.publish('case01',ticket(key,p,'case01',nonce='b'*64))
    assert next_result['tip_sha256']!=first['tip_sha256']
    assert recovered.audit()['length']==2
