"""CH40-D fresh mathematical witnesses: source pinning, directed rounding, attack tests."""
import copy,hashlib,json,pathlib,sys,unittest,zipfile
from fractions import Fraction as F
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from verify_original40 import decode_case,ORIGINAL_ZIP_SHA256
from witness_producer40d import direct_witness,coupled_witness,taylor_witness,newton_witness
from witness_checker40d import verify
from rational_kernel40d import R
from checker_interval40d import Z
ARCHIVE=ROOT/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'

class ProofWitnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()!=ORIGINAL_ZIP_SHA256:raise RuntimeError('Untrusted frozen original')
        with zipfile.ZipFile(ARCHIVE) as z:
            pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
            cls.cert=decode_case(z,'one_event_n80_i00',pins)
            cls.zero=decode_case(z,'zero_imbalanced_n160_i05',pins)
        cls.d=direct_witness(cls.cert,0)
        cls.c=coupled_witness(cls.cert,0)
        cls.t=taylor_witness(cls.cert,0)
        cls.n=newton_witness(cls.cert,0)
    def refuses(self,base,edit):
        w=copy.deepcopy(base);edit(w)
        with self.assertRaises((ValueError,ArithmeticError,KeyError,TypeError,IndexError)):
            verify(self.cert,w)
    def test_01_frozen_original_sha256(self):self.assertEqual(hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),ORIGINAL_ZIP_SHA256)
    def test_02_direct_full_interval_trace(self):self.assertTrue(verify(self.cert,self.d)['valid_local_witness'])
    def test_03_coupled_full_row_tangent_trace(self):self.assertTrue(verify(self.cert,self.c)['valid_local_witness'])
    def test_04_taylor_hessian_remainder(self):self.assertTrue(verify(self.cert,self.t)['taylor_expansion_certified'])
    def test_05_newton_contract_valid(self):self.assertTrue(verify(self.cert,self.n)['stationary_contraction_certified'])
    def test_06_all_scoped_no_global_release(self):
        for w in (self.d,self.c,self.t,self.n):
            r=verify(self.cert,w)
            self.assertFalse(r['global_optimality_certified'])
            self.assertEqual(r['scientific_release'],'NO_GO')
    def test_07_wrong_checkpoint(self):self.refuses(self.c,lambda w:w.__setitem__('certificate_sha256','0'*64))
    def test_08_wrong_model_pin(self):self.refuses(self.d,lambda w:w.__setitem__('model_sha256','0'*64))
    def test_09_forge_source_node_box(self):self.refuses(self.c,lambda w:w['box'][0].__setitem__(0,'-9'))
    def test_10_wrong_source_node_id(self):self.refuses(self.c,lambda w:w.__setitem__('node_id',1))
    def test_11_forge_scientific_promotion(self):self.refuses(self.d,lambda w:w.__setitem__('scientific_release','GO'))
    def test_12_forge_direct_bound(self):self.refuses(self.d,lambda w:w['claim'].__setitem__('upper','-100000'))
    def test_13_forge_direct_likelihood_row(self):self.refuses(self.d,lambda w:w['arithmetic_trace']['loglik_rows'][0].__setitem__(1,'-100000'))
    def test_14_forge_fisher_determinant_interval(self):self.refuses(self.d,lambda w:w['arithmetic_trace'].__setitem__('fisher_determinant',['1','1']))
    def test_15_forge_tangent_point(self):self.refuses(self.c,lambda w:w['support']['tangent_points'].__setitem__(0,'0'))
    def test_16_forge_tangent_score(self):self.refuses(self.c,lambda w:w['arithmetic_trace']['tangent_support_evaluations'][0].__setitem__('slope',['0','0']))
    def test_17_forge_tangent_value(self):self.refuses(self.c,lambda w:w['arithmetic_trace']['tangent_support_evaluations'][0].__setitem__('value',['0','0']))
    def test_18_forge_tangent_upper(self):self.refuses(self.c,lambda w:w['claim'].__setitem__('upper','-100000'))
    def test_19_forge_tangent_term(self):self.refuses(self.c,lambda w:w['arithmetic_trace']['tangent_terms'][0].__setitem__(1,'-100000'))
    def test_20_missing_tangent_row(self):self.refuses(self.c,lambda w:w['arithmetic_trace']['tangent_terms'].pop())
    def test_21_forge_taylor_midpoint(self):self.refuses(self.t,lambda w:w['taylor_support']['midpoint'].__setitem__(0,'0'))
    def test_22_forge_taylor_value(self):self.refuses(self.t,lambda w:w['taylor_support'].__setitem__('f0',['0','0']))
    def test_23_forge_taylor_gradient(self):self.refuses(self.t,lambda w:w['taylor_support']['gradient'].__setitem__(0,['0','0']))
    def test_24_forge_taylor_hessian(self):self.refuses(self.t,lambda w:w['taylor_support']['hessian'][0].__setitem__(0,['0','0']))
    def test_25_forge_taylor_upper(self):self.refuses(self.t,lambda w:w['claim'].__setitem__('upper','-100000'))
    def test_26_forge_newton_contraction(self):self.refuses(self.n,lambda w:w['claim']['box'][0].__setitem__(0,w['claim']['box'][0][1]))
    def test_27_forge_newton_hessian(self):self.refuses(self.n,lambda w:w['newton_support']['hessian_box'][0].__setitem__(0,['0','0']))
    def test_28_forge_newton_krawczyk(self):self.refuses(self.n,lambda w:w['newton_support']['krawczyk_enclosure'].__setitem__(0,['0','0']))
    def test_29_forge_newton_root(self):self.refuses(self.n,lambda w:w['root_box'][0].__setitem__(0,'-9'))
    def test_30_forge_newton_exclusion(self):
        def change(w):w['claim']={'status':'NO_STATIONARY','reason':'GRADIENT_SIGN'}
        self.refuses(self.n,change)
    def test_31_forge_newton_preconditioner(self):self.refuses(self.n,lambda w:w['newton_support']['preconditioner'][0].__setitem__(0,'1000'))
    def test_32_forge_newton_local_box(self):self.refuses(self.n,lambda w:w['local_box'][0].__setitem__(0,'-10'))
    def test_33_reject_other_protocol(self):self.refuses(self.c,lambda w:w.__setitem__('protocol','CH40C-FAKE'))
    def test_34_rational_exact_mul_div(self):
        x=R('0.1','0.3');y=R('0.4','0.9')
        self.assertEqual((x*y).lo,F(4,100));self.assertEqual((x*y).hi,F(27,100))
        self.assertEqual((x/y).lo,F(1,9));self.assertEqual((x/y).hi,F(3,4))
    def test_35_directed_decimal_kernel(self):
        x=Z('0.1','0.3');y=Z('0.4','0.9');z=x/y
        self.assertTrue(F(z.lo)<=F(1,9) and F(z.hi)>=F(3,4))
    def test_36_strict_zero_imbalanced_hessian(self):
        # The original v0 emitter had silently truncated 1e28 Hessian displays
        # to Python's default 28-digit context; must now be independently safe.
        w=taylor_witness(self.zero,0)
        self.assertTrue(verify(self.zero,w)['taylor_expansion_certified'])

if __name__=='__main__':unittest.main(verbosity=2)