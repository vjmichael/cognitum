"""Optional independent SciPy assignment parity: mathematical optimality only."""
import random
import unittest
try:
    from scipy.optimize import linear_sum_assignment
except ImportError:
    linear_sum_assignment=None
from cognitum import spatial_identity_association as engine
from tests.test_c15_p2b_identity_association import seed,observed,request

@unittest.skipUnless(linear_sum_assignment is not None,'SciPy optional')
class P2BAssignmentParity(unittest.TestCase):
    def test_30_seeded_three_by_three_scipy_assignment_parity(self):
        for j in range(30):
            rng=random.Random(9000+j)
            xs=sorted(rng.sample(range(-80,80),3))
            ys=[x+rng.uniform(-.3,.3) for x in xs]
            rng.shuffle(ys)
            state=seed([observed(f't{i}',x) for i,x in enumerate(xs)])
            r=request(state,[(f'o{i}',y) for i,y in enumerate(ys)],
                      sigma=2.,speed=100.,cost=1000.,k=3)
            h=engine.propose(state,r)
            # Engine sorts observation IDs, and object IDs, just like the matrix.
            matrix=[[.5*((y-x)/2)**2 for x in xs] for y in ys]
            rows,cols=linear_sum_assignment(matrix)
            expected={f'o{i}':f't{col}' for i,col in zip(rows,cols)}
            found={pair.observation_id:pair.object_id for pair in h.hypotheses[0].pairs}
            self.assertEqual(found,expected)
            self.assertFalse(h.grants_authority)

    def test_31_bounded_six_by_six_enumeration(self):
        state=seed([observed(f't{i}',i*5) for i in range(6)])
        r=request(state,[(f'o{i}',i*5+.01) for i in range(6)],sigma=1,
                  speed=100,cost=50,k=8)
        h=engine.propose(state,r)
        self.assertEqual(len(h.hypotheses),8)
        self.assertEqual(len(h.hypotheses[0].pairs),6)
        self.assertTrue(engine.verify_proposal(state,r,h))

if __name__=='__main__':unittest.main()
