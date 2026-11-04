"""Research-only regression gates. Missing optional native library => explicit skip."""
import json,os,sys,unittest,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
try:
    import flint
except ImportError:
    flint=None

class SourceContractTests(unittest.TestCase):
    def test_frozen_input_pins_exist_and_are_distinct(self):
        try:
            from run_m5 import load_cases
        except ModuleNotFoundError as exc:
            self.skipTest('Native backend missing: '+str(exc))
        root=Path(os.environ.get('CH40M_TRACES','/nonexistent'))
        pins=Path(os.environ.get('CH40M_PINS','/nonexistent'))
        if not root.is_dir() or not pins.is_file():self.skipTest('External original frozen sources unavailable')
        self.assertEqual(len(load_cases(root,pins)),15)
    def test_missing_original_refusal(self):
        if flint is None:self.skipTest('FLINT absent')
        from run_m5 import load_cases
        from tempfile import TemporaryDirectory
        pins=Path(os.environ.get('CH40M_PINS','/nonexistent'))
        if not pins.is_file():self.skipTest('Original pins unavailable')
        with TemporaryDirectory() as d:
            bad=Path(d)/'bad';bad.mkdir()
            (bad/'quasi_separated_n80_i00_127_original_mpfr_trace.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'15 original files'):
                load_cases(bad,pins)
    def test_wrong_hash_pin_refused(self):
        if flint is None:self.skipTest('FLINT absent')
        from run_m5 import load_cases
        from tempfile import TemporaryDirectory
        traces=Path(os.environ.get('CH40M_TRACES','/nonexistent'))
        pins=Path(os.environ.get('CH40M_PINS','/nonexistent'))
        if not traces.is_dir() or not pins.is_file():self.skipTest('Original immutable traces unavailable')
        copy=json.loads(pins.read_text())
        copy['cases'][0]['trace_sha256']='0'*64
        with TemporaryDirectory() as d:
            modified=Path(d)/'modified_pins.json'
            modified.write_text(json.dumps(copy))
            with self.assertRaisesRegex(ValueError,'Trace SHA pin mismatch'):
                load_cases(traces,modified)

@unittest.skipIf(flint is None,'Native python-flint unavailable')
class FLINTTests(unittest.TestCase):
    def setUp(self):
        from gram_psd import gram3,det3,native_cap,eta_extrema,weight_upper_endpoints
        self.gram3=gram3;self.det3=det3;self.native_cap=native_cap
        self.eta_extrema=eta_extrema;self.weight_upper_endpoints=weight_upper_endpoints
        self.rows=[{'x':['1','0','0'],'n':1,'s':0},{'x':['0','1','0'],'n':1,'s':1},{'x':['0','0','1'],'n':1,'s':0}]
        self.cert={'model':{'d':3,'rows':self.rows,'n_raw':3}}
    def test_gram_exact(self):
        from fractions import Fraction as F
        m=self.gram3(self.rows,[F(1,4)]*3)
        self.assertEqual(self.det3(m),F(1,64))
    def test_correlation_beats_hadamard(self):
        from fractions import Fraction as F
        rows=[{'x':['1','1','0'],'n':1},{'x':['1','0','1'],'n':1},{'x':['1','-1','-1'],'n':1}]
        m=self.gram3(rows,[F(1,4)]*3)
        self.assertGreater(m[0][0]*m[1][1]*m[2][2],self.det3(m))
    def test_exact_linear_endpoints(self):
        from fractions import Fraction as F
        self.assertEqual(self.eta_extrema({'x':['1','-2','3']},[['1','2'],['-1','4'],['0','1']]),(F(-7),F(7)))
    def test_inverted_box_refused(self):
        with self.assertRaisesRegex(ValueError,'Reversed'):self.eta_extrema(self.rows[0],[['2','1'],['0','1'],['0','1']])
    def test_weight_maximum(self):
        from fractions import Fraction as F
        self.assertEqual(self.weight_upper_endpoints(F(-3),F(4)),F(1,4))
        self.assertLess(self.weight_upper_endpoints(F(2),F(3)),F(1,4))
    def test_noninteger_count_refused(self):
        cert={'model':{'d':3,'rows':[dict(self.rows[0]),dict(self.rows[1]),dict(self.rows[2])]}}
        cert['model']['rows'][0]['n']=1.5
        with self.assertRaisesRegex(ValueError,'integer counts'):
            self.native_cap(cert,[['-1','1']]*3)
    def test_rank_deficient_refused(self):
        cert={'model':{'d':3,'rows':[self.rows[0]]*3}}
        with self.assertRaisesRegex(ArithmeticError,'positive Fisher'):
            self.native_cap(cert,[['-1','1']]*3)
    def test_precision_restored_and_ordered(self):
        old=flint.ctx.prec
        a=self.native_cap(self.cert,[['-1','1']]*3,prec=192)
        self.assertEqual(flint.ctx.prec,old)
        self.assertLessEqual(a['gram_upper'],a['hadamard_upper'])
    def test_replay_tampering_refused(self):
        from independent_psd_check import validate_native
        c=self.native_cap(self.cert,[['-1','1']]*3)
        directory=Path(os.environ.get('CH40M_CHECKER','/nonexistent'))
        if not directory.is_dir():self.skipTest('Independent checker unavailable')
        self.assertEqual(validate_native(self.cert,[['-1','1']]*3,c,directory)['status'],'ACCEPTED_CONSERVATIVE_PSD_GRAM_UPPER')
        c['weights_upper'][0]=0
        with self.assertRaisesRegex(ArithmeticError,'weight'):
            validate_native(self.cert,[['-1','1']]*3,c,directory)
    def test_original_15(self):
        from run_m5 import load_cases
        from independent_psd_check import validate_native
        traces=Path(os.environ.get('CH40M_TRACES','/nonexistent'))
        pins=Path(os.environ.get('CH40M_PINS','/nonexistent'))
        checker=Path(os.environ.get('CH40M_CHECKER','/nonexistent'))
        if not traces.is_dir() or not pins.is_file() or not checker.is_dir():self.skipTest('Frozen original evidence not available')
        c=load_cases(traces,pins)
        for name,sha,cert in c:
            with self.subTest(case=name):
                leaf=max((n for n in cert['nodes'] if not n.get('children')),key=lambda n:n['upper_bound_ceil_display'])
                res=self.native_cap(cert,leaf['effective_box'])
                self.assertEqual(validate_native(cert,leaf['effective_box'],res,checker)['status'],'ACCEPTED_CONSERVATIVE_PSD_GRAM_UPPER')

if __name__=='__main__':unittest.main()
