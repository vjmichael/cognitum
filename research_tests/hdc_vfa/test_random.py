import unittest
import numpy as np
from cognitum.research.vfa_random import Basis, Function

def gauss(x,m,s): return np.exp(-0.5*((x-m)/s)**2)
def spectrum(w,m,s): return np.sqrt(2*np.pi)*s*np.exp(-0.5*(s*w)**2+1j*m*w)

class TestVFA(unittest.TestCase):
    def setUp(self):
        self.b=Basis.random(1024,8,13); self.w=self.b.omega
        self.f=Function(self.b,spectrum(self.w,.5,1.1)); self.g=Function(self.b,spectrum(self.w,-.4,.7)); self.x=np.linspace(-3,3,37)
    def test_binding_positions(self): np.testing.assert_allclose(self.b.encode(.23)*self.b.encode(-1.18),self.b.encode(-.95),atol=2e-15)
    def test_inverse_position(self): np.testing.assert_allclose(self.b.encode(.73)*self.b.encode(-.73),1,atol=2e-15)
    def test_add(self): np.testing.assert_allclose((self.f+self.g).evaluate(self.x),self.f.evaluate(self.x)+self.g.evaluate(self.x),atol=1e-13)
    def test_sub(self): np.testing.assert_allclose((self.f-self.g).evaluate(self.x),self.f.evaluate(self.x)-self.g.evaluate(self.x),atol=1e-13)
    def test_scale(self): np.testing.assert_allclose(self.f.scale(-2.3).evaluate(self.x),-2.3*self.f.evaluate(self.x),atol=1e-13)
    def test_translation(self): np.testing.assert_allclose(self.f.translate(.2).evaluate(self.x),self.f.evaluate(self.x-.2),atol=1e-13)
    def test_convolution(self):
        np.testing.assert_allclose(self.f.convolve(self.g).coeff,spectrum(self.w,.1,np.hypot(1.1,.7))*np.sqrt(2*np.pi)*1.1*.7/np.hypot(1.1,.7),atol=2e-14)
    def test_convolution_not_pointwise(self): self.assertGreater(np.max(np.abs(self.f.convolve(self.g).evaluate(self.x)-self.f.evaluate(self.x)*self.g.evaluate(self.x))),.5)
    def test_derivative(self): np.testing.assert_allclose(self.f.derivative().evaluate(self.x),(self.f.evaluate(self.x+1e-5)-self.f.evaluate(self.x-1e-5))/2e-5,atol=1e-8)
    def test_sample_encoding(self):
        grid=np.linspace(-9,9,901); a=self.b.from_samples(grid,gauss(grid,.5,1.1)); np.testing.assert_allclose(a.coeff,self.f.coeff,atol=1e-12)
    def test_incompatible(self):
        with self.assertRaises(ValueError): self.f.convolve(Function(Basis.random(1024,8,14),self.g.coeff))
    def test_nonfinite(self):
        for fun in (lambda: self.f.evaluate(np.nan),lambda: self.f.scale(np.inf),lambda: self.b.encode(np.nan),lambda: Function(self.b,self.f.coeff*np.nan)):
            with self.assertRaises(ValueError): fun()
    def test_invalid_samples(self):
        with self.assertRaises(ValueError): self.b.from_samples([0,0],[1,1])
    def test_scalar_and_shape(self):
        self.assertIsInstance(self.f.evaluate(0),float); self.assertEqual(self.f.evaluate(np.zeros((2,3))).shape,(2,3))
    def test_snapshot(self):
        original=self.f.coeff.copy(); fn=Function(self.b,original); original[:]=0; np.testing.assert_array_equal(fn.coeff,self.f.coeff)
    def test_immutable_basis_and_coeff(self):
        for a in (self.f.coeff,self.b.omega):
            with self.assertRaises(ValueError): a.setflags(write=True)
    def test_distributive(self): np.testing.assert_allclose(self.f.convolve(self.g+self.f).coeff,(self.f.convolve(self.g)+self.f.convolve(self.f)).coeff,atol=1e-13)
if __name__=='__main__': unittest.main()
