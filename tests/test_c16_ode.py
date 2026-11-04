"""C16 genuine SciPy ODE acceptance with analytic and invariant reference cases."""
from dataclasses import replace
from math import pi,exp,sqrt
import unittest
from cognitum.physics_ode import PhysicalModel,validate,integrate,compare_refinement


def harmonic(method="DOP853"):
    return PhysicalModel(
        kind="harmonic",unit_system="SI:m,s,kg,N",
        mass_kg=2.,spring_n_per_m=8.,damping_n_s_per_m=0.,
        force_n=0.,gravity_m_per_s2=0.,
        initial_position_m=1.,initial_velocity_m_per_s=0.,
        t_end_s=pi,output_steps=64,rtol=1e-9,atol=1e-11,
        method=method,max_internal_step_s=.02,
    )


class C16ODETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from scipy.integrate import solve_ivp
        except ImportError:
            raise unittest.SkipTest("optional SciPy ODE backend not installed")

    def test_scipy_analytic_harmonic_reference_and_energy(self):
        for method in ("RK45","DOP853","Radau","BDF"):
            with self.subTest(method=method):
                p=harmonic(method)
                r=integrate(p)
                self.assertEqual(r.status,"OK")
                self.assertEqual(len(r.samples),65)
                self.assertTrue(r.reached_end)
                self.assertLess(r.convergence_max_error_m,2e-5)
                self.assertLess(r.max_balance_residual_j,1e-3)
                self.assertLess(r.max_invariant_relative_drift,1e-3)
                self.assertAlmostEqual(r.samples[-1].position_m,1.,places=4)
                self.assertGreater(r.function_evals,0)

    def test_independent_tighter_solver_disagreement(self):
        first=compare_refinement(harmonic("RK45"))
        self.assertEqual(first.status,"COMPARED")
        self.assertLess(first.max_position_disagreement_m,2e-5)
        self.assertLess(first.max_velocity_disagreement_m_per_s,2e-5)
        self.assertGreater(first.refined_evaluations,0)
        self.assertIn("not_rigorous_error_bound","_".join(first.limitations))

    def test_forced_and_damped_energy_balance(self):
        base=harmonic("RK45")
        for kind,force in (("damped",0.),("forced",1.)):
            p=replace(base,kind=kind,force_n=force,damping_n_s_per_m=.3)
            r=integrate(p)
            self.assertEqual(r.status,"OK")
            self.assertLess(r.max_balance_residual_j,3e-3)
            self.assertIsNone(r.convergence_max_error_m)

    def test_falling_drag_and_terminal_boundary(self):
        p=replace(harmonic(),kind="falling_drag",spring_n_per_m=0.,
                  damping_n_s_per_m=.5,gravity_m_per_s2=9.81,
                  initial_position_m=10.,t_end_s=5.,
                  stop_at_position_m=0.)
        r=integrate(p)
        self.assertEqual(r.status,"EVENT_STOP")
        self.assertFalse(r.reached_end)
        self.assertIsNotNone(r.event_time_s)
        self.assertAlmostEqual(r.samples[-1].position_m,0.,places=5)
        self.assertLess(r.max_balance_residual_j,1e-2)

    def test_finite_domain_and_budget_fail_closed(self):
        p=replace(harmonic(),max_function_evals=50,method="RK45",
                  max_internal_step_s=.001)
        r=integrate(p)
        self.assertEqual(r.status,"UNKNOWN_RESOURCE_OR_NUMERICAL_FAILURE")
        self.assertFalse(r.samples)

    def test_invalid_units_method_nonfinite_and_boundary_rejected(self):
        p=harmonic()
        bad=(
            replace(p,unit_system="ft,s,slug"),
            replace(p,kind="eval_source"),
            replace(p,method="custom_exec"),
            replace(p,mass_kg=0.),
            replace(p,spring_n_per_m=-1.),
            replace(p,damping_n_s_per_m=1.),
            replace(p,initial_velocity_m_per_s=float("nan")),
            replace(p,rtol=0.),
            replace(p,atol=1e-20),
            replace(p,output_steps=257),
            replace(p,max_internal_step_s=0.),
            replace(p,t_end_s=1001),
            replace(p,stop_at_position_m=2.),
            replace(p,max_function_evals=True),
        )
        for b in bad:
            with self.subTest(case=repr(b)[:90]),self.assertRaises(ValueError):
                validate(b)


if __name__=="__main__":
    unittest.main()
