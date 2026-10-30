"""C11 P1 focused contract, math, adverse-input and real-HiGHS smoke tests."""
import hashlib
import random
import unittest

from cognitum.optimization import (
    OptimizationRegistry, _compile, _exact_certificate, _valid_assignment, _value,
    make_optimization_audit, verify_optimization_frame,
)
from cognitum.proto import optimization_pb2 as p


def req(*, backend='scipy-highs', top=4, exact=0):
    r = p.OptimizeRequest(schema_version=1, backend_id=backend, timeout_ms=1000,
                          trace_id='c11-functional', max_exact_states=exact)
    r.variables.add(name='x', lower=0, upper=top)
    r.variables.add(name='y', lower=0, upper=4)
    r.objective.sense = p.MAXIMIZE
    r.objective.terms.add(variable='x', coefficient=3)
    r.objective.terms.add(variable='y', coefficient=2)
    c = r.constraints.add(relation=p.LESS_EQUAL, rhs=7, label='capacity')
    c.terms.add(variable='x', coefficient=2)
    c.terms.add(variable='y', coefficient=1)
    return r


def encode(x):
    return x.SerializeToString(deterministic=True)


class C11Tests(unittest.TestCase):
    def setUp(self):
        self.reg = OptimizationRegistry(enabled=True)

    def call(self, r):
        frame = encode(r)
        return frame, p.OptimizeResult.FromString(self.reg.run_frame(frame, host_authorized=True))

    def test_real_highs_optimum(self):
        frame, out = self.call(req())
        self.assertEqual(out.status, p.VERIFIED_OPTIMAL)
        self.assertEqual(out.objective_value, 12)
        self.assertEqual([(x.name, x.value) for x in out.assignment], [('x', 2), ('y', 3)])
        self.assertTrue(out.optimality_verified)
        self.assertIn('HiGHS', out.backend_version)
        check = p.OptimizeReceipt.FromString(verify_optimization_frame(frame, encode(out)))
        self.assertTrue(check.evidence_valid)
        self.assertTrue(check.optimality_verified)
        self.assertEqual(check.states_checked, 25)

    def test_minimization_exact(self):
        r = req()
        r.objective.sense = p.MINIMIZE
        r.objective.ClearField('terms')
        r.objective.terms.add(variable='x', coefficient=1)
        r.ClearField('constraints')
        c = r.constraints.add(relation=p.GREATER_EQUAL, rhs=2)
        c.terms.add(variable='x', coefficient=1)
        _, out = self.call(r)
        self.assertEqual(out.objective_value, 2)
        self.assertEqual(out.status, p.VERIFIED_OPTIMAL)

    def test_infeasible_exhaustive(self):
        r = req()
        r.ClearField('constraints')
        c = r.constraints.add(relation=p.GREATER_EQUAL, rhs=5)
        c.terms.add(variable='x', coefficient=1)
        frame, out = self.call(r)
        self.assertEqual(out.status, p.VERIFIED_INFEASIBLE)
        self.assertFalse(out.witness_verified)
        self.assertTrue(p.OptimizeReceipt.FromString(verify_optimization_frame(frame, encode(out))).optimality_verified)

    def test_large_domain_feasible_not_certified_optimal(self):
        r = req(top=1_000_000)
        r.ClearField('constraints')
        frame, out = self.call(r)
        self.assertEqual(out.status, p.VERIFIED_FEASIBLE)
        self.assertTrue(out.witness_verified)
        self.assertFalse(out.optimality_verified)
        chk = p.OptimizeReceipt.FromString(verify_optimization_frame(frame, encode(out)))
        self.assertTrue(chk.evidence_valid)
        self.assertFalse(chk.optimality_verified)

    def test_large_domain_infeasible_claim_stays_unknown(self):
        r = req(top=1_000_000)
        r.ClearField('constraints')
        c = r.constraints.add(relation=p.GREATER_EQUAL, rhs=1_000_000)
        c.terms.add(variable='x', coefficient=1)
        c = r.constraints.add(relation=p.LESS_EQUAL, rhs=999_999)
        c.terms.add(variable='x', coefficient=1)
        _, out = self.call(r)
        self.assertEqual(out.status, p.UNKNOWN)
        self.assertEqual(out.backend_claim, 'INFEASIBLE')

    def test_neither_registration_nor_host_authority_can_be_skipped(self):
        r = req()
        frame = encode(r)
        denied = p.OptimizeResult.FromString(self.reg.run_frame(frame))
        self.assertEqual(denied.status, p.REJECTED)
        self.reg.disable()
        denied2 = p.OptimizeResult.FromString(self.reg.run_frame(frame, host_authorized=True))
        self.assertEqual(denied2.reason_code, 'REGISTRY_DISABLED')
        self.assertFalse(denied2.host_approved)

    def test_backend_absent_returns_unknown(self):
        r = req(backend='ortools-cpsat')
        _, out = self.call(r)
        try:
            import ortools  # noqa F401
        except ImportError:
            self.assertEqual(out.status, p.UNKNOWN)
            self.assertEqual(out.reason_code, 'BACKEND_NOT_AVAILABLE')
        else:
            self.assertEqual(out.status, p.VERIFIED_OPTIMAL)

    def test_unknown_backend_rejected(self):
        r = req(backend='shell-injection')
        _, out = self.call(r)
        self.assertEqual(out.status, p.REJECTED)

    def test_missing_objective_rejected(self):
        r = req(); r.ClearField('objective')
        _, out = self.call(r)
        self.assertEqual(out.status, p.REJECTED)

    def test_duplicate_terms_rejected(self):
        r = req(); r.objective.terms.add(variable='x', coefficient=5)
        _, out = self.call(r)
        self.assertEqual(out.status, p.REJECTED)

    def test_undeclared_terms_rejected(self):
        r = req(); r.objective.terms.add(variable='other', coefficient=5)
        _, out = self.call(r)
        self.assertEqual(out.status, p.REJECTED)

    def test_invalid_limits_rejected(self):
        r = req(); r.timeout_ms = 5001
        _, out = self.call(r)
        self.assertEqual(out.status, p.REJECTED)
        r = req(); r.max_exact_states = 4097
        _, out = self.call(r)
        self.assertEqual(out.status, p.REJECTED)

    def test_invalid_binary_domain_rejected(self):
        r = req(); r.variables[0].binary = True
        _, out = self.call(r)
        self.assertEqual(out.status, p.REJECTED)

    def test_invalid_version_rejected(self):
        r = req(); r.schema_version = 2
        _, out = self.call(r)
        self.assertEqual(out.status, p.REJECTED)

    def test_malformed_wire_rejected(self):
        with self.assertRaises(ValueError):
            self.reg.run_frame(b'\xff\xff', host_authorized=True)

    def test_noncanonical_wire_rejected(self):
        with self.assertRaises(ValueError):
            self.reg.run_frame(encode(req()) + b'\x08\x01', host_authorized=True)

    def test_proof_rejects_tampered_objective(self):
        frame, out = self.call(req())
        out.objective_value += 1
        check = p.OptimizeReceipt.FromString(verify_optimization_frame(frame, encode(out)))
        self.assertFalse(check.evidence_valid)

    def test_proof_rejects_forged_optimal_flag_large(self):
        frame, out = self.call(req(top=1_000_000))
        # The model still satisfies the constraints, but the full domain wasn't checked.
        out.status = p.VERIFIED_OPTIMAL
        out.optimality_verified = True
        check = p.OptimizeReceipt.FromString(verify_optimization_frame(frame, encode(out)))
        self.assertFalse(check.evidence_valid)

    def test_proof_rejects_host_approval_and_trace_spoof(self):
        frame, out = self.call(req())
        out.host_approved = True
        self.assertFalse(p.OptimizeReceipt.FromString(verify_optimization_frame(frame, encode(out))).evidence_valid)
        out.host_approved = False
        out.trace_id = 'different'
        self.assertFalse(p.OptimizeReceipt.FromString(verify_optimization_frame(frame, encode(out))).evidence_valid)

    def test_proof_rejects_cross_request_replay(self):
        frame, out = self.call(req())
        other = req(); other.constraints[0].rhs = 8
        self.assertFalse(p.OptimizeReceipt.FromString(verify_optimization_frame(encode(other), encode(out))).evidence_valid)

    def test_proof_rejects_false_infeasible(self):
        frame, out = self.call(req())
        out.status = p.VERIFIED_INFEASIBLE
        del out.assignment[:]
        out.witness_verified = False
        self.assertFalse(p.OptimizeReceipt.FromString(verify_optimization_frame(frame, encode(out))).evidence_valid)

    def test_forged_solver_witness_downgrades_unknown(self):
        self.reg.backends['scipy-highs'] = lambda pr, tm: ('OPTIMAL', (99., 99.), 'host-test-fake')
        _, out = self.call(req())
        self.assertEqual(out.status, p.UNKNOWN)
        self.assertFalse(out.witness_verified)

    def test_solver_false_infeasibility_downgrades_unknown(self):
        self.reg.backends['scipy-highs'] = lambda pr, tm: ('INFEASIBLE', None, 'host-test-fake')
        _, out = self.call(req())
        self.assertEqual(out.status, p.UNKNOWN)

    def test_solver_suboptimal_witness_not_optimum(self):
        self.reg.backends['scipy-highs'] = lambda pr, tm: ('OPTIMAL', (0., 0.), 'host-test-fake')
        frame, out = self.call(req())
        self.assertEqual(out.status, p.VERIFIED_FEASIBLE)
        self.assertFalse(out.optimality_verified)
        self.assertTrue(p.OptimizeReceipt.FromString(verify_optimization_frame(frame, encode(out))).evidence_valid)

    def test_audit_is_data_minimized_and_bound(self):
        frame, out = self.call(req())
        audit_bytes = make_optimization_audit(frame, encode(out))
        audit = p.OptimizationAudit.FromString(audit_bytes)
        self.assertEqual(audit.request_sha256, hashlib.sha256(frame).digest())
        self.assertEqual(audit.result_sha256, hashlib.sha256(encode(out)).digest())
        self.assertEqual(audit.backend_id, 'scipy-highs')
        self.assertNotIn(b'capacity', audit_bytes)
        self.assertFalse(audit.host_approved)
        out.trace_id = 'forged'
        with self.assertRaises(ValueError):
            make_optimization_audit(frame, encode(out))

    def test_audit_rejects_forged_proof(self):
        frame, out = self.call(req())
        out.objective_value = 999
        with self.assertRaises(ValueError):
            make_optimization_audit(frame, encode(out))

    def test_equality_binary_and_negative_objective(self):
        r = req()
        r.variables[0].upper = 1
        r.variables[0].binary = True
        r.ClearField('constraints')
        c = r.constraints.add(relation=p.EQUAL, rhs=2)
        c.terms.add(variable='x', coefficient=1)
        c.terms.add(variable='y', coefficient=1)
        r.objective.sense = p.MINIMIZE
        r.objective.terms[0].coefficient = -10
        frame, out = self.call(r)
        self.assertEqual(out.status, p.VERIFIED_OPTIMAL)
        self.assertEqual(out.objective_value, -8)
        self.assertTrue(p.OptimizeReceipt.FromString(verify_optimization_frame(frame, encode(out))).evidence_valid)

    def test_constant_infeasible_row(self):
        r = req(); r.ClearField('constraints')
        r.constraints.add(relation=p.LESS_EQUAL, rhs=-1)
        frame, out = self.call(r)
        self.assertEqual(out.status, p.VERIFIED_INFEASIBLE)
        self.assertTrue(p.OptimizeReceipt.FromString(verify_optimization_frame(frame, encode(out))).evidence_valid)

    def test_pure_exact_constraint_oracle(self):
        randomizer = random.Random(1101)
        for _ in range(40):
            r = req(top=3)
            r.constraints[0].rhs = randomizer.randrange(-2, 9)
            r.objective.terms[0].coefficient = randomizer.randrange(-4, 5)
            r.objective.terms[1].coefficient = randomizer.randrange(-4, 5)
            pr = _compile(r)
            best, _, cases = _exact_certificate(pr)
            assert cases == 20
            candidates = [tuple(vals) for vals in __import__('itertools').product(range(4), range(5)) if _valid_assignment(pr, vals)]
            scores = [_value(pr, x) for x in candidates]
            self.assertEqual(best, max(scores) if scores else None)

    def test_real_highs_small_random_feasible_and_infeasible(self):
        randomizer = random.Random(1912)
        for _ in range(8):
            r = req(top=2)
            r.constraints[0].rhs = randomizer.randrange(-2, 7)
            r.objective.terms[0].coefficient = randomizer.randrange(-3, 4)
            r.objective.terms[1].coefficient = randomizer.randrange(-3, 4)
            frame, out = self.call(r)
            self.assertIn(out.status, (p.VERIFIED_OPTIMAL, p.VERIFIED_INFEASIBLE))
            receipt = p.OptimizeReceipt.FromString(verify_optimization_frame(frame, encode(out)))
            self.assertTrue(receipt.evidence_valid)
            self.assertTrue(receipt.optimality_verified)


if __name__ == '__main__':
    unittest.main()
