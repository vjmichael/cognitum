"""C16 typed ODE wire execution and adversarial result-replay tests."""
from dataclasses import replace
from math import pi
import unittest
from cognitum.proto import physics_ode_pb2 as pb
from cognitum.physics_ode_wire import execute,verify


def request():
    p=pb.PhysicalRequest(
        schema_version=1,kind="harmonic",unit_system="SI:m,s,kg,N",
        mass_kg=2,spring_n_per_m=8,damping_n_s_per_m=0,
        force_n=0,gravity_m_per_s2=0,
        initial_position_m=1,initial_velocity_m_per_s=0,
        t_end_s=pi,output_steps=40,rtol=1e-9,atol=1e-11,
        method="DOP853",max_internal_step_s=.02,
        max_function_evals=20000,validation_domain="idealized_reference")
    return p.SerializeToString(deterministic=True)


class C16WireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from scipy.integrate import solve_ivp
        except ImportError:
            raise unittest.SkipTest("optional SciPy ODE backend not installed")

    def test_real_scipy_typed_trajectory_and_verification(self):
        try:
            import scipy
        except ImportError:
            self.skipTest("SciPy not installed")
        raw=request()
        reply=verify(raw,execute(raw))
        self.assertEqual(reply.status,"OK")
        self.assertTrue(reply.has_balance)
        self.assertTrue(reply.has_analytic_comparison)
        self.assertEqual(len(reply.samples),41)
        self.assertLess(reply.convergence_max_error_m,1e-5)

    def test_tampering_and_cross_request_rejected(self):
        raw=request()
        answer=pb.PhysicalResult()
        answer.ParseFromString(execute(raw))
        answer.samples[1].position_m+=0.1
        with self.assertRaises(ValueError):
            verify(raw,answer.SerializeToString(deterministic=True))
        answer.ParseFromString(execute(raw))
        answer.request_sha256="0"*64
        with self.assertRaises(ValueError):
            verify(raw,answer.SerializeToString(deterministic=True))

    def test_unknown_protobuf_and_invalid_units_rejected(self):
        raw=request()
        for invalid in (b"",raw+b"\x98\x06\x01",raw+b"\x08\x01",
                        b"\x0a\xff",b"x"*8193):
            with self.subTest(input=invalid[:10]),self.assertRaises(ValueError):
                execute(invalid)
        r=pb.PhysicalRequest()
        r.ParseFromString(raw)
        r.unit_system="imperial:feet,second,slug"
        with self.assertRaises(ValueError):
            execute(r.SerializeToString(deterministic=True))

    def test_event_boundary_and_implicit_method(self):
        r=pb.PhysicalRequest()
        r.ParseFromString(request())
        r.kind="falling_drag"
        r.spring_n_per_m=0
        r.damping_n_s_per_m=1
        r.gravity_m_per_s2=9.81
        r.initial_position_m=10
        r.t_end_s=5
        r.method="Radau"
        r.has_stop_boundary=True
        r.stop_at_position_m=0
        raw=r.SerializeToString(deterministic=True)
        result=verify(raw,execute(raw))
        self.assertEqual(result.status,"EVENT_STOP")
        self.assertTrue(result.has_event)
        self.assertFalse(result.reached_end)
        self.assertAlmostEqual(result.samples[-1].position_m,0,places=5)


if __name__=="__main__":
    unittest.main()
