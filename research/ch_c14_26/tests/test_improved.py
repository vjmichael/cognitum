import json,sys,unittest
from pathlib import Path
sys.path.insert(0,'/mnt/data/CH_C14_24')
sys.path.insert(0,'/mnt/data/CH_C14_26')
from verified_bnb import logistic_model,FirthObjective,interval_box
from improved_bounds import ImprovedObjective
from mpfr_interval import Interval as I,MP
D=Path('/mnt/data/CH_C14_25/inputs')
class TestOriginals(unittest.TestCase):
    def data(self,name):
        x=json.loads((D/f'{name}.json').read_text()); d=logistic_model(x['rows'])
        return x,FirthObjective(d),ImprovedObjective(d)
    def test_fifteen_roots_contain_baseline_point(self):
        for p in sorted(D.glob('*.json')):
            with self.subTest(p.name):
                dat,old,new=self.data(p.stem)
                box=interval_box(dat['bounds'])
                upper,_=new.objective(box)
                midpoint=['-4.5','0','0']
                fv,_=old.objective([I(v) for v in midpoint])
                self.assertGreaterEqual(upper.hi.cmp(fv.lo),0)
    def test_tightbox_analytic_derivatives_enclose_jet(self):
        x,old,new=self.data('zero_balanced_n80_i00')
        box=interval_box([['-4.5','-4.49'],['0','0.01'],['0','0.01']])
        ours_g,ours_h=new.analytic_derivatives(box)
        old_jet=old.jet([I('-4.495'),I('0.005'),I('0.005')])
        for j in range(3):
            self.assertLessEqual(ours_g[j].lo.cmp(old_jet.g[j].lo),0)
            self.assertGreaterEqual(ours_g[j].hi.cmp(old_jet.g[j].hi),0)
            for k in range(3):
                self.assertLessEqual(ours_h[j][k].lo.cmp(old_jet.h[j][k].lo),0)
                self.assertGreaterEqual(ours_h[j][k].hi.cmp(old_jet.h[j][k].hi),0)
    def test_gram_vs_hadamard(self):
        inp,old,new=self.data('rare_5pct_n80_i00')
        a,_=old.objective(interval_box(inp['bounds']))
        b,_=new.objective(interval_box(inp['bounds']))
        self.assertLess(b.hi.cmp(a.hi),0)
if __name__=='__main__':unittest.main()
