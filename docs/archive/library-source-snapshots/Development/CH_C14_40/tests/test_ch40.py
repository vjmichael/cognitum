"""Adversarial/positive CH40-A tests on the unchanged original CH39 archive."""
from __future__ import annotations
import base64, copy, hashlib, json, pathlib, sys, unittest, zipfile
from decimal import Decimal, localcontext
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from exact_decimal40 import IV, trans, CONTEXT
from independent_checker40 import MathematicalModel,verify_certificate,exact_partition,model_check,validate_duals
from verify_original40 import decode_case,verify_archive,ORIGINAL_ZIP_SHA256
ARCHIVE=ROOT/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
if not ARCHIVE.is_file():
 ARCHIVE=pathlib.Path('/mnt/data/Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip')
CASE='one_event_n80_i00'

class CH40(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with zipfile.ZipFile(ARCHIVE) as z:
   pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
   cls.pins=pins;cls.cert=decode_case(z,CASE,pins)
 @staticmethod
 def mutate(data, mutator):
  c=copy.deepcopy(data);mutator(c);return c
 def test_00_independent_original_127_nodes_64_leaves(self):
  q=verify_certificate(self.cert)
  self.assertEqual(q['nodes_geometry_verified'],127)
  self.assertEqual(q['leaf_bounds_independently_recomputed'],64)
  self.assertFalse(q['bounded_gap_proven_by_independent_checker'])
  self.assertEqual(q['scientific_release'],'NO_GO')
 def test_01_one_ulp_log_and_exp_bracket(self):
  for x in ['-10','-0.25','0','1.5','20']:
   a=IV(x);y=a.exp();self.assertLess(y.lo,y.hi)
   with localcontext(CONTEXT):
    reference=Decimal(x).exp()
   self.assertLessEqual(y.lo,reference);self.assertGreaterEqual(y.hi,reference)
  for x in ['0.000001','1','1.5','200']:
   a=IV(x);y=a.ln()
   with localcontext(CONTEXT):
    reference=Decimal(x).ln()
   self.assertLessEqual(y.lo,reference);self.assertGreaterEqual(y.hi,reference)
 def test_02_no_floating_inputs(self):
  with self.assertRaises(TypeError):IV(0.1)
 def test_03_nonpositive_log_fails_closed(self):
  with self.assertRaises(ArithmeticError):IV(-1,1).ln()
 def test_04_invalid_interval_division_fails_closed(self):
  with self.assertRaises(ArithmeticError):IV(1)/IV(-1,1)
 def test_05_original_checkpoint_file_pin(self):
  with zipfile.ZipFile(ARCHIVE) as z:
   raw=z.read('CH_C14_33/active/'+CASE+'/checkpoint.json')
  self.assertEqual(hashlib.sha256(raw).hexdigest(),self.pins[CASE]['checkpoint_file_sha256'])
  self.assertEqual(hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),ORIGINAL_ZIP_SHA256)
 def test_06_changed_root_partition_refused(self):
  c=self.mutate(self.cert,lambda c:c['nodes'][0]['box'][0].__setitem__(1,'100'))
  with self.assertRaises(ValueError):exact_partition(c)
 def test_07_duplicate_child_refused(self):
  c=self.mutate(self.cert,lambda c:c['nodes'][0].__setitem__('children',[1,1]))
  with self.assertRaises(ValueError):exact_partition(c)
 def test_08_fake_newton_contraction_refused(self):
  c=self.mutate(self.cert,lambda c:c['nodes'][0].__setitem__('effective_box',[['-9','1'],['-5','5'],['-5','5']]))
  with self.assertRaises(ValueError):exact_partition(c)
 def test_09_wrong_parent_refused(self):
  c=self.mutate(self.cert,lambda c:c['nodes'][1].__setitem__('parent_id',2))
  with self.assertRaises(ValueError):exact_partition(c)
 def test_10_non_spd_matrix_refused(self):
  c=self.mutate(self.cert,lambda c:c['dual_matrices'][0][0].__setitem__(0,'-1'))
  with self.assertRaises(ValueError):validate_duals(c)
 def test_11_non_symmetric_matrix_refused(self):
  c=self.mutate(self.cert,lambda c:c['dual_matrices'][0][0].__setitem__(1,'55'))
  with self.assertRaises(ValueError):validate_duals(c)
 def test_12_changed_model_digest_refused(self):
  c=self.mutate(self.cert,lambda c:c['model']['rows'][0].__setitem__('s',1))
  with self.assertRaises(ValueError):verify_certificate(c)
 def test_13_no_premature_release(self):
  c=self.mutate(self.cert,lambda c:c.__setitem__('production_release','GO'))
  with self.assertRaises(ValueError):verify_certificate(c)
 def test_14_finite_domain_not_Rd(self):
  c=self.mutate(self.cert,lambda c:c.__setitem__('unbounded_global_claim',True))
  with self.assertRaises(ValueError):verify_certificate(c)
 def test_15_fake_certification_rejected(self):
  c=self.mutate(self.cert,lambda c:c.__setitem__('status','CERTIFIED_BOUNDED_GAP'))
  with self.assertRaises(ValueError):verify_certificate(c)
 def test_16_incumbent_outside_box_rejected(self):
  c=self.mutate(self.cert,lambda c:c['incumbent'].__setitem__(0,'200'))
  with self.assertRaises(ValueError):verify_certificate(c)
 def test_17_producer_display_not_authoritative(self):
  # Display field is not proof input. Real bounds derive from inputs/maths.
  c=self.mutate(self.cert,lambda c:c['nodes'][0].__setitem__('local_upper_bound_display',-1e9))
  self.assertEqual(exact_partition(c),exact_partition(self.cert))
 def test_18_independent_point_enclosure(self):
  model=MathematicalModel(self.cert['model']);inc=self.cert['incumbent']
  self.assertLessEqual(model.incumbent_lower(inc),model.objective_bound([(v,v) for v in inc]))

if __name__=='__main__':unittest.main(verbosity=2)