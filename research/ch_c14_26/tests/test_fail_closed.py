"""CH26 adversarial proof-record and original-data authentication tests."""
import copy,hashlib,json,sys,unittest
from pathlib import Path
D=Path(__file__).resolve().parents[1];C=D.parent/'CH_C14_25'
if not C.exists():C=D.parent/'ch_c14_25'
sys.path.insert(0,str(D))
from verifier26 import verify
P=json.loads((D/'frozen_protocol.json').read_text())
CASE='rare_5pct_n80_i00'
class FailClosed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cert=json.loads((D/'certificates'/f'{CASE}.json').read_text())
        cls.inp=json.loads((C/'inputs'/f'{CASE}.json').read_text())
    def test_original_case_identity(self):
        known=next(x for x in P['cases'] if x['id']==CASE)
        self.assertEqual(hashlib.sha256((C/'inputs'/f'{CASE}.json').read_bytes()).hexdigest(),known['exact_input_sha256'])
        self.assertEqual(self.inp['original_CH23_identity']['data_digest'],known['original_digest'])
    def test_refuses_tampered_partition(self):
        c=copy.deepcopy(self.cert)
        c['nodes'][1]['box'][0][0]='-9.9'
        with self.assertRaises(ValueError):verify(c,self.inp,P)
    def test_refuses_tampered_tangent_anchor(self):
        c=copy.deepcopy(self.cert)
        c['tangent_anchors'][0][0]='-4.0'
        with self.assertRaises(ValueError):verify(c,self.inp,P)
    def test_refuses_tampered_frozen_identity(self):
        c=copy.deepcopy(self.cert)
        c['original_data_identity']['data_digest']='0'*64
        with self.assertRaises(ValueError):verify(c,self.inp,P)
    def test_refuses_fake_bounded_optimality(self):
        c=copy.deepcopy(self.cert)
        self.assertEqual(c['status'],'UNRESOLVED_REFUSE_CERTIFICATION')
        c['status']='CERTIFIED_BOUNDED_GAP'
        with self.assertRaisesRegex(ValueError,'False certified gap'):verify(c,self.inp,P)
    def test_fixed_original_coefficient_box(self):
        self.assertEqual(self.cert['root_box'],[['-10','1'],['-5','5'],['-5','5']])
        self.assertEqual(self.cert['claim_scope'],'finite_root_box_only')
        self.assertFalse(self.cert['unbounded_global_claim'])
if __name__=='__main__':unittest.main()
