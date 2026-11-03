import sys,pathlib,copy,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research_receipt40f import *
CASE='one_event_n80_i00';H='a'*64;PIN1='b'*64
PIN_DATA={CASE:{'original_head_sha256':'c'*64,'checkpoint_sha256':'d'*64}}
BASE={'protocol':PROTOCOL,'case_id':CASE,'nonce':H,'policy_sha256':PIN1,
'original_archive_sha256':PIN,'original_case_sha256':'e'*64,
'original_head_sha256':'c'*64,'checkpoint_sha256':'d'*64,'certificate_sha256':'f'*64,
'producer_trace_sha256':'1'*64,'node_count':127,'direct_caps_certified':83,
'coupled_caps_certified':44,'inherited_caps_certified':127,'unsupported_caps':0,
'scope':SCOPE,'checker_result':'INDEPENDENT_MATH_CERTIFIED_FINITE_CAPS','scientific_release':'NO_GO',
'global_optimality_certified':False,'attestation_policy':'RESEARCH_ONLY_NEVER_PRODUCTION_OR_SCIENTIFIC_GO'}
class Tests(unittest.TestCase):
 def call(self,body,seen=None,uid=1004,nonce=H,policy=PIN1,case=CASE,trace='1'*64):
  return attestor_research_guard(body,trusted_peer_uid=uid,checker_uid=1004,
         nonce=nonce,policy_hash=policy,case=case,pins=PIN_DATA,source_trace_sha=trace,
         expected_case_hash='e'*64,expected_certificate_sha='f'*64,used_nonces=set() if seen is None else seen)
 def test_valid_research_only(self):
  r=self.call(BASE);self.assertTrue(r['accepted']);self.assertFalse(r['production_admission'])
 def test_replay(self):
  seen=set();self.call(BASE,seen)
  with self.assertRaises(Refusal):self.call(BASE,seen)
 def test_missing_field(self):
  o=BASE.copy();o.pop('scope')
  with self.assertRaises(Refusal):self.call(o)
 def test_extra_global_field(self):
  o=BASE.copy();o['release']='GO'
  with self.assertRaises(Refusal):self.call(o)
 def test_changed_peer_uid(self):
  with self.assertRaises(Refusal):self.call(BASE,uid=1002)
 def test_global_optimum_forgery(self):
  o=BASE.copy();o['global_optimality_certified']=True
  with self.assertRaises(Refusal):self.call(o)
 def test_scientific_promotion(self):
  o=BASE.copy();o['scientific_release']='GO'
  with self.assertRaises(Refusal):self.call(o)
 def test_case_source_hash(self):
  o=BASE.copy();o['original_case_sha256']='0'*64
  with self.assertRaises(Refusal):self.call(o)
 def test_certificate_sha(self):
  o=BASE.copy();o['certificate_sha256']='0'*64
  with self.assertRaises(Refusal):self.call(o)
 def test_source_zip_forgery(self):
  o=BASE.copy();o['original_archive_sha256']='0'*64
  with self.assertRaises(Refusal):self.call(o)
 def test_missing_cap(self):
  o=BASE.copy();o['coupled_caps_certified']=43
  with self.assertRaises(Refusal):self.call(o)
 def test_unsupported_cap(self):
  o=BASE.copy();o['unsupported_caps']=1
  with self.assertRaises(Refusal):self.call(o)
 def test_inherited(self):
  o=BASE.copy();o['inherited_caps_certified']=126
  with self.assertRaises(Refusal):self.call(o)
 def test_pin(self):
  o=BASE.copy();o['checkpoint_sha256']='0'*64
  with self.assertRaises(Refusal):self.call(o)
 def test_nonce(self):
  with self.assertRaises(Refusal):self.call(BASE,nonce='2'*64)
 def test_trace_hash(self):
  with self.assertRaises(Refusal):self.call(BASE,trace='3'*64)
 def test_policy(self):
  with self.assertRaises(Refusal):self.call(BASE,policy='4'*64)
 def test_case(self):
  with self.assertRaises(Refusal):self.call(BASE,case='other')
 def test_wrong_types(self):
  o=BASE.copy();o['node_count']=True
  with self.assertRaises(Refusal):self.call(o)
 def test_scope(self):
  o=BASE.copy();o['scope']='PRODUCTION'
  with self.assertRaises(Refusal):self.call(o)
 def test_ch39_downgrade(self):
  o=BASE.copy();o['protocol']='CH39-CHECKER-V1'
  with self.assertRaises(Refusal):self.call(o)
if __name__=='__main__':unittest.main()
