"""Independent cryptographic and antirollback refusal tests for the public M11 chain."""
from __future__ import annotations
import base64,copy,json,pathlib,sys,unittest
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from public_audit_m11 import verify,Refusal

class PublicChainTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    p=HERE/'M11_PUBLIC_CHAIN.json'
    if not p.exists():raise unittest.SkipTest('Public signed research evidence not bundled')
    cls.doc=json.loads(p.read_text())
    cls.reference=verify(cls.doc)
 def test_all15_public_evidence(self):
    self.assertEqual((self.reference['cases'],self.reference['signed_child_coverage']),(15,296))
    self.assertFalse(self.reference['math_independently_recomputed_in_this_public_audit'])
 def test_external_trusted_pins_pass(self):
    x=verify(self.doc,expected_anchor_tip=self.reference['anchor_tip'],
           expected_anchor_key_sha=self.reference['anchor_public_sha256'],
           expected_verifier_key_sha=self.reference['verifier_public_sha256'])
    self.assertEqual(x,self.reference)
 def test_forged_verifier_signature_refused(self):
    x=copy.deepcopy(self.doc);x['checkpoint_rows'][0]['signature_b64']=base64.b64encode(b'\x00'*64).decode()
    with self.assertRaises(Refusal):verify(x)
 def test_forged_anchor_signature_refused(self):
    x=copy.deepcopy(self.doc);x['anchor']['entries'][0]['signature']=base64.b64encode(b'\x00'*64).decode()
    with self.assertRaises(Refusal):verify(x)
 def test_mutated_signed_receipt_refused(self):
    x=copy.deepcopy(self.doc);p=x['checkpoint_rows'][0];raw=base64.b64decode(p['body_b64']);raw=raw.replace(b'NO_GO',b'NO_GX',1)
    p['body_b64']=base64.b64encode(raw).decode()
    with self.assertRaises(Refusal):verify(x)
 def test_external_anchor_tip_detects_rollback(self):
    with self.assertRaisesRegex(Refusal,'ROLLBACK'):
       verify(self.doc,expected_anchor_tip='0'*64)
 def test_external_anchor_key_identity_detects_substitution(self):
    with self.assertRaisesRegex(Refusal,'identity'):
       verify(self.doc,expected_anchor_key_sha='0'*64)
 def test_anchor_checkpoint_tip_mismatch_refused(self):
    x=copy.deepcopy(self.doc);x['anchor']['entries'][8]['event']['checkpoint_tip']='0'*64
    with self.assertRaises(Refusal):verify(x)
 def test_anchor_event_reordering_refused(self):
    x=copy.deepcopy(self.doc);x['anchor']['entries'][0],x['anchor']['entries'][1]=x['anchor']['entries'][1],x['anchor']['entries'][0]
    with self.assertRaises(Refusal):verify(x)
if __name__=='__main__':unittest.main(verbosity=2)
