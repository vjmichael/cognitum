import sys,json,base64,copy,hashlib,zipfile,pytest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from caps_policy40g import PINNED,SCOPE,validate_caps
from protocol39 import V_DOMAIN,S_DOMAIN,canonical,objhash,sha,verify_ticket,verify_signature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
R=Path(__file__).resolve().parents[2]/'assets'/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
CASE='one_event_n80_i00'
Z=zipfile.ZipFile(R)
PINS=json.loads(Z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
oldrec=next(json.loads(Z.read(n)) for n in Z.namelist() if n.startswith('CH_C14_39/CH39_public_witness/revisions/') and json.loads(Z.read(n))['body']['case_id']==CASE)
ATT=oldrec['body']['attestor_ticket']['body']['attestation']
NONCE='a'*64
POLICY=objhash(PINS)
KEY=Ed25519PrivateKey.generate()
PEM=KEY.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)


def caps():
 f=PINNED[CASE];pin=PINS[CASE]
 return {'protocol':'CH40F-CHECKER-FINITE-ROOT-CAPS-V1','case_id':CASE,'nonce':NONCE,'policy_sha256':POLICY,
 'original_archive_sha256':'9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b',
 'original_case_sha256':f['original_case_sha256'],'original_head_sha256':pin['original_head_sha256'],
 'checkpoint_sha256':pin['checkpoint_sha256'],'certificate_sha256':f['certificate_sha256'],
 'producer_trace_sha256':f['trace_sha256'],'node_count':127,'direct_caps_certified':83,'coupled_caps_certified':44,
 'inherited_caps_certified':127,'unsupported_caps':0,'scope':SCOPE,
 'checker_result':'INDEPENDENT_MATH_CERTIFIED_FINITE_CAPS','scientific_release':'NO_GO',
 'global_optimality_certified':False,'attestation_policy':'RESEARCH_ONLY_NEVER_PRODUCTION_OR_SCIENTIFIC_GO'}

def ticket(cap=None,domain=V_DOMAIN):
 cap=caps() if cap is None else cap
 result={'version':1,'nonce':NONCE,'case_id':CASE,'policy_sha256':POLICY,'attestor_fingerprint_sha256':sha(PEM),
 'attestation':ATT,'checker_receipt':{'version':1,'case_id':CASE,'nonce':NONCE,'policy_sha256':POLICY,
 'worker_attestation_sha256':objhash(ATT),'checker_attestation_sha256':objhash(ATT),
 'checker_result':'INDEPENDENT_REPLAY_ACCEPTED','checker_scope':'FROZEN_CH23_127_NODES_6_FRAMES_MPFR_224'},
 'caps_receipt':cap}
 return {'body':result,'signature':base64.b64encode(KEY.sign(domain+canonical(result))).decode('ascii')}

def verify(t):return verify_ticket(t,PEM,sha(PEM),POLICY,CASE,NONCE,PINS)

def test_valid_research_ticket():assert verify(ticket())==ATT

@pytest.mark.parametrize('field,val',[
 ('producer_trace_sha256','0'*64),('certificate_sha256','0'*64),('original_case_sha256','0'*64),
 ('original_head_sha256','0'*64),('checkpoint_sha256','0'*64),('nonce','0'*64),
 ('policy_sha256','0'*64),('scientific_release','GO'),('global_optimality_certified',True),
 ('scope','PRODUCTION'),('attestation_policy','ACCEPT_GLOBAL'),('node_count',126),
 ('unsupported_caps',1),('inherited_caps_certified',126),('direct_caps_certified',82),('coupled_caps_certified',45),
 ('protocol','CH39'),('checker_result','TRUST_THE_WORKER'),
])
def test_reject_changed_caps(field,val):
 c=caps();c[field]=val
 with pytest.raises(ValueError):verify(ticket(c))

def test_reject_swapped_direct_and_coupled_counts():
 c=caps();c['direct_caps_certified']=82;c['coupled_caps_certified']=45
 with pytest.raises(ValueError):verify(ticket(c))

def test_reject_extra_receipt_key():
 c=caps();c['extra']='yes'
 with pytest.raises(ValueError):verify(ticket(c))

def test_refuse_legacy_signature_domain():
 with pytest.raises(ValueError):verify(ticket(domain=b'Cognitum/CH39/attestor-uid-mpfr-result/v1\x00'))

def test_refuse_tampered_signature():
 t=ticket();t['body']['caps_receipt']['node_count']=13
 with pytest.raises(ValueError):verify(t)

def test_refuse_other_public_key():
 wrong=Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
 with pytest.raises(ValueError):verify_ticket(ticket(),wrong,sha(wrong),POLICY,CASE,NONCE,PINS)


def test_signature_domain_not_historical_ch39():
 with pytest.raises(ValueError):verify_signature(ticket(),PEM,b'Cognitum/CH39/attestor-uid-mpfr-result/v1\x00')