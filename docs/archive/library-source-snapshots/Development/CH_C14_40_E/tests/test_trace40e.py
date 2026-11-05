"""CH40-E trace corruption/refusal tests: frozen original data only, no synthetic case replacements."""
from __future__ import annotations
import unittest,copy,json,sys,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from verify_trace40e import verify,Refusal,dyad,interval
from fractions import Fraction
ARCHIVE=(ROOT/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip') if (ROOT/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip').exists() else pathlib.Path('/mnt/data/Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip')
ORIGINAL=json.loads((ROOT/'results'/'one_event_n80_i00_1_original_mpfr_trace.json').read_text())

def change_first_bit(record, field, value):
    record[field]['significand']=value

class OriginalProducerTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.r=ORIGINAL
    def test_root_complete_producer_direct_and_coupled(self):
        r=verify(copy.deepcopy(self.r),ARCHIVE)
        self.assertEqual(r['checks']['nodes'],1)
        self.assertTrue(r['all_recorded_selected_caps_certified'])
    def test_canonical_dyad_fraction(self):
        self.assertEqual(dyad({'significand':'101','exponent':2}),Fraction(5,2))
        self.assertEqual(dyad({'significand':'-1','exponent':-1}),Fraction(-1,4))
    def test_empty_dyad_refused(self):
        with self.assertRaises(Refusal):dyad({'significand':'','exponent':0})
    def test_tampered_mpfr_effective_cap(self):
        q=copy.deepcopy(self.r);q['nodes'][0]['effective_cap']['significand']='1'
        with self.assertRaises(Refusal):verify(q,ARCHIVE)
    def test_forged_dual_index(self):
        q=copy.deepcopy(self.r);q['nodes'][0]['dual_candidates'][0]['q_index']=9999
        with self.assertRaises(Refusal):verify(q,ARCHIVE)
    def test_tangent_support_moved(self):
        q=copy.deepcopy(self.r);q['nodes'][0]['dual_candidates'][0]['rows'][0]['p0_decimal']='0.123456789'
        with self.assertRaises(Refusal):verify(q,ARCHIVE)
    def test_missing_tangent_row(self):
        q=copy.deepcopy(self.r);q['nodes'][0]['dual_candidates'][0]['rows'].pop()
        with self.assertRaises(Refusal):verify(q,ARCHIVE)
    def test_narrowed_tangent_value(self):
        q=copy.deepcopy(self.r);x=q['nodes'][0]['dual_candidates'][0]['rows'][0]['g_value'];x[1]=x[0]
        with self.assertRaises(Refusal):verify(q,ARCHIVE)
    def test_too_small_dual_kappa(self):
        q=copy.deepcopy(self.r);q['nodes'][0]['dual_candidates'][0]['kappa'][0]={'significand':'1','exponent':-50}
        with self.assertRaises(Refusal):verify(q,ARCHIVE)
    def test_narrowed_fisher_weight(self):
        q=copy.deepcopy(self.r);x=q['nodes'][0]['direct_trace']['rows'][0]['w'];x[1]=x[0]
        with self.assertRaises(Refusal):verify(q,ARCHIVE)
    def test_inconsistent_direct_fisher_det(self):
        q=copy.deepcopy(self.r);x=q['nodes'][0]['direct_trace']['det_enclosure'];x[1]=x[0]
        with self.assertRaises(Refusal):verify(q,ARCHIVE)
    def test_missing_producer_tangent(self):
        q=copy.deepcopy(self.r);q['nodes'][0]['direct_trace']['tangent_anchors']=[]
        with self.assertRaises(Refusal):verify(q,ARCHIVE)
    def test_unknown_original_data(self):
        q=copy.deepcopy(self.r);q['case']='other_unfrozen_dataset'
        with self.assertRaises((Refusal,KeyError)):verify(q,ARCHIVE)
    def test_newton_not_traced_refusal(self):
        q=copy.deepcopy(self.r);q['certificate']['nodes'][0]['newton']={'status':'CONTRACTED'}
        with self.assertRaises(Refusal):verify(q,ARCHIVE)
    def test_scientific_promotion_refusal(self):
        q=copy.deepcopy(self.r);q['scientific_release']='GO'
        with self.assertRaises(Refusal):verify(q,ARCHIVE)
    def test_malformed_source_hash(self):
        q=copy.deepcopy(self.r);q['certificate_sha256']='0'*64
        with self.assertRaises(Refusal):verify(q,ARCHIVE)
    def test_root_box_modification(self):
        q=copy.deepcopy(self.r);q['certificate']['root_box'][0][0]='-12345'
        with self.assertRaises(Refusal):verify(q,ARCHIVE)

if __name__=='__main__':unittest.main()