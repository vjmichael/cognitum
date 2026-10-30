"""C10 P3 focused functionality and adversarial proof tests; no benchmarks."""
import copy
import hashlib
from pathlib import Path
import unittest

from cognitum.proto import formal_advanced_pb2 as a, formal_backend_pb2 as b
from cognitum.formal_backend import ApprovedBackend,SolverRegistry
from cognitum.formal_finite import prove_finite_frame,verify_finite_frame
from cognitum.formal_session import run_session_frame,verify_session_frame,_contexts


def wire(x):return x.SerializeToString(deterministic=True)
def variable(name):return b.Expr(variable=name)
def neg(x):return b.Expr(application=b.Application(op=b.NOT,args=[x]))
def gt(name,number):return b.Expr(application=b.Application(op=b.GT,args=[variable(name),b.Expr(integer=b.IntegerLiteral(decimal=str(number)))]))
def lt(name,number):return b.Expr(application=b.Application(op=b.LT,args=[variable(name),b.Expr(integer=b.IntegerLiteral(decimal=str(number)))]))
def eq(x,y):return b.Expr(application=b.Application(op=b.EQ,args=[x,y]))
def bv(number,width):return b.Expr(bitvector=b.BitVectorLiteral(value=number,width=width))

def base(kind=b.BOOL):
    p=a.SessionPlan(schema_version=1,backend_id='z3-lib',trace_id='p3-functional')
    p.variables.add(name='x',sort=kind,width=2 if kind==b.BV else 0)
    return p

def get_registry():
    lib=Path('/lib/x86_64-linux-gnu/libz3.so.4')
    if not lib.is_file():return None
    return SolverRegistry((ApprovedBackend('z3-lib','z3-lib',str(lib),hashlib.sha256(lib.read_bytes()).hexdigest()),))

class FiniteTests(unittest.TestCase):
    def check_finite(self,run):
        frame=wire(run); proof=prove_finite_frame(frame)
        return a.FiniteCertificate.FromString(proof),verify_finite_frame(frame,proof),frame,proof

    def test_bool_contradiction_has_independent_certificate(self):
        run=b.BackendRun(schema_version=1)
        run.variables.add(name='x',sort=b.BOOL);run.assertions.extend([variable('x'),neg(variable('x'))])
        cert,ok,_,_=self.check_finite(run)
        self.assertTrue(ok);self.assertTrue(cert.unsat_verified);self.assertEqual(cert.cases_checked,2)

    def test_bool_sat_no_unsat_certificate(self):
        run=b.BackendRun(schema_version=1)
        run.variables.add(name='x',sort=b.BOOL);run.assertions.extend([variable('x')])
        cert,ok,_,_=self.check_finite(run)
        self.assertFalse(ok);self.assertFalse(cert.unsat_verified);self.assertEqual(cert.cases_checked,2)

    def test_empty_universe_false_is_certified(self):
        run=b.BackendRun(schema_version=1,assertions=[b.Expr(boolean=False)])
        cert,ok,_,_=self.check_finite(run);self.assertTrue(ok);self.assertEqual(cert.cases_checked,1)

    def test_bv_exhaustive_and_modular_wrap(self):
        run=b.BackendRun(schema_version=1)
        run.variables.add(name='x',sort=b.BV,width=2)
        plus=b.Expr(application=b.Application(op=b.BVADD,args=[variable('x'),bv(1,2)]))
        run.assertions.extend([eq(plus,bv(0,2)),eq(variable('x'),bv(0,2))])
        cert,ok,_,_=self.check_finite(run);self.assertTrue(ok);self.assertEqual(cert.cases_checked,4)

    def test_bv_sat_wrap_counterexample(self):
        run=b.BackendRun(schema_version=1)
        run.variables.add(name='x',sort=b.BV,width=2)
        plus=b.Expr(application=b.Application(op=b.BVADD,args=[variable('x'),bv(1,2)]))
        run.assertions.extend([eq(plus,bv(0,2)),eq(variable('x'),bv(3,2))])
        cert,ok,_,_=self.check_finite(run);self.assertFalse(ok)

    def test_integer_variable_fails_closed(self):
        run=b.BackendRun(schema_version=1)
        run.variables.add(name='x',sort=b.INT)
        run.assertions.extend([gt('x',2),lt('x',0)])
        cert,ok,_,_=self.check_finite(run);self.assertFalse(ok);self.assertFalse(cert.unsat_verified)
        self.assertEqual(cert.reason_code,'UNSUPPORTED_PROOF_THEORY')

    def test_large_domain_abstains(self):
        run=b.BackendRun(schema_version=1)
        run.variables.add(name='x',sort=b.BV,width=13)
        run.assertions.extend([b.Expr(boolean=False)])
        cert,ok,_,_=self.check_finite(run);self.assertFalse(ok)
        self.assertEqual(cert.reason_code,'FINITE_PROOF_BUDGET')

    def test_tampered_proof_never_passes(self):
        run=b.BackendRun(schema_version=1,assertions=[b.Expr(boolean=False)])
        cert,ok,frame,proof=self.check_finite(run);self.assertTrue(ok)
        for edit in ('request_sha256','cases_checked','exhaustive_sha256','reason_code','unsat_verified'):
            bad=a.FiniteCertificate.FromString(proof)
            setattr(bad,edit,{'request_sha256':b'bad','cases_checked':3,'exhaustive_sha256':b'bad','reason_code':'FORGED','unsat_verified':False}[edit])
            self.assertFalse(verify_finite_frame(frame,wire(bad)),edit)

    def test_mismatched_request_denied(self):
        one=b.BackendRun(schema_version=1,assertions=[b.Expr(boolean=False)])
        two=b.BackendRun(schema_version=1,assertions=[b.Expr(boolean=True)])
        self.assertFalse(verify_finite_frame(wire(two),prove_finite_frame(wire(one))))

class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.reg=get_registry()
    def run_case(self,plan):
        if not self.reg:self.skipTest('optional local Z3 shared library unavailable')
        frame=wire(plan);return frame,a.SessionResult.FromString(run_session_frame(frame,self.reg,host_authorized=True))

    def test_real_incremental_push_pop_three_checks(self):
        plan=base();plan.steps.add(kind=a.SessionStep.ASSERT,assertion=variable('x'))
        plan.steps.add(kind=a.SessionStep.CHECK,label='before')
        plan.steps.add(kind=a.SessionStep.PUSH)
        plan.steps.add(kind=a.SessionStep.ASSERT,assertion=neg(variable('x')))
        plan.steps.add(kind=a.SessionStep.CHECK,label='during')
        plan.steps.add(kind=a.SessionStep.POP)
        plan.steps.add(kind=a.SessionStep.CHECK,label='after')
        script,_=_contexts(plan)
        self.assertEqual(script.count('(check-sat)'),3)
        self.assertIn('(push 1)',script);self.assertIn('(pop 1)',script)
        frame,out=self.run_case(plan)
        self.assertTrue(out.completed,out.reason_code)
        self.assertEqual([x.backend_result.verdict for x in out.checkpoints],[b.SAT,b.UNSAT,b.SAT])
        self.assertEqual(out.checkpoints[1].core_assertion_step_indices[:],[1,4])
        self.assertTrue(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)

    def test_assumptions_are_ephemeral(self):
        plan=base();plan.steps.add(kind=a.SessionStep.ASSERT,assertion=variable('x'))
        plan.steps.add(kind=a.SessionStep.CHECK,assumptions=[neg(variable('x'))])
        plan.steps.add(kind=a.SessionStep.CHECK)
        frame,out=self.run_case(plan)
        self.assertEqual([x.backend_result.verdict for x in out.checkpoints],[b.UNSAT,b.SAT])
        self.assertEqual(out.checkpoints[0].core_assumption_indices[:],[1])
        self.assertEqual(out.checkpoints[0].core_assertion_step_indices[:],[1])
        self.assertTrue(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)

    def test_finite_bv_core(self):
        plan=base(b.BV)
        plan.steps.add(kind=a.SessionStep.ASSERT,assertion=eq(variable('x'),bv(1,2)))
        plan.steps.add(kind=a.SessionStep.CHECK,assumptions=[eq(variable('x'),bv(2,2))])
        frame,out=self.run_case(plan)
        self.assertEqual(out.checkpoints[0].backend_result.verdict,b.UNSAT)
        self.assertTrue(out.checkpoints[0].core_independently_verified)
        self.assertTrue(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)

    def test_integer_unsat_claim_not_a_proof(self):
        plan=base(b.INT)
        plan.steps.add(kind=a.SessionStep.ASSERT,assertion=gt('x',2))
        plan.steps.add(kind=a.SessionStep.CHECK,assumptions=[lt('x',0)])
        frame,out=self.run_case(plan)
        self.assertEqual(out.checkpoints[0].backend_result.verdict,b.UNSAT)
        self.assertEqual(out.checkpoints[0].reason_code,'UNSAT_NOT_INDEPENDENTLY_PROVEN')
        self.assertFalse(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)

    def test_host_required(self):
        plan=base();plan.steps.add(kind=a.SessionStep.CHECK)
        res=a.SessionResult.FromString(run_session_frame(wire(plan),self.reg or SolverRegistry(),host_authorized=False))
        self.assertFalse(res.completed);self.assertEqual(res.reason_code,'HOST_AUTHORIZATION_REQUIRED')

    def test_registry_disable(self):
        reg=get_registry();plan=base();plan.steps.add(kind=a.SessionStep.CHECK)
        if not reg:self.skipTest('optional Z3 unavailable')
        reg.disable()
        res=a.SessionResult.FromString(run_session_frame(wire(plan),reg,host_authorized=True))
        self.assertEqual(res.reason_code,'REGISTRY_DISABLED')

    def test_mutating_model_rejected_by_receipt(self):
        plan=base();plan.steps.add(kind=a.SessionStep.ASSERT,assertion=variable('x'));plan.steps.add(kind=a.SessionStep.CHECK)
        frame,out=self.run_case(plan)
        self.assertTrue(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)
        out.checkpoints[0].backend_result.model[0].exact_value='0'
        self.assertFalse(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)

    def test_tampered_core_rejected(self):
        plan=base();plan.steps.add(kind=a.SessionStep.ASSERT,assertion=variable('x'))
        plan.steps.add(kind=a.SessionStep.CHECK,assumptions=[neg(variable('x'))])
        frame,out=self.run_case(plan)
        self.assertTrue(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)
        out.checkpoints[0].core_assumption_indices[0]=2
        self.assertFalse(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)

    def test_tampered_certificate_rejected(self):
        plan=base();plan.steps.add(kind=a.SessionStep.ASSERT,assertion=variable('x'))
        plan.steps.add(kind=a.SessionStep.CHECK,assumptions=[neg(variable('x'))])
        frame,out=self.run_case(plan)
        out.checkpoints[0].finite_certificate.exhaustive_sha256=b'forged'
        self.assertFalse(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)

    def test_forged_unsat_host_assurance_rejected(self):
        plan=base();plan.steps.add(kind=a.SessionStep.ASSERT,assertion=variable('x'))
        plan.steps.add(kind=a.SessionStep.CHECK,assumptions=[neg(variable('x'))])
        frame,out=self.run_case(plan)
        self.assertTrue(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)
        out.checkpoints[0].backend_result.host_approved=True
        self.assertFalse(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)
        out.checkpoints[0].backend_result.host_approved=False
        out.checkpoints[0].backend_result.semantic_formalization_verified=True
        self.assertFalse(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)

    def test_fake_unsat_backend_evidence_rejected(self):
        plan=base();plan.steps.add(kind=a.SessionStep.ASSERT,assertion=variable('x'))
        plan.steps.add(kind=a.SessionStep.CHECK,assumptions=[neg(variable('x'))])
        frame,out=self.run_case(plan)
        out.checkpoints[0].backend_result.verification=b.SAT_WITNESS_CHECKED
        self.assertFalse(a.SessionReceipt.FromString(verify_session_frame(frame,wire(out))).evidence_valid)

    def test_tampered_plan_rejected(self):
        plan=base();plan.steps.add(kind=a.SessionStep.CHECK)
        frame,out=self.run_case(plan)
        plan.steps[0].label='modified'
        self.assertFalse(a.SessionReceipt.FromString(verify_session_frame(wire(plan),wire(out))).evidence_valid)

    def test_unclosed_scope_rejected(self):
        plan=base();plan.steps.add(kind=a.SessionStep.PUSH);plan.steps.add(kind=a.SessionStep.CHECK)
        _,out=self.run_case(plan)
        self.assertFalse(out.completed);self.assertEqual(out.reason_code,'UNCLOSED_PUSH_SCOPE')

    def test_pop_without_push_rejected(self):
        plan=base();plan.steps.add(kind=a.SessionStep.POP);plan.steps.add(kind=a.SessionStep.CHECK)
        _,out=self.run_case(plan)
        self.assertFalse(out.completed);self.assertEqual(out.reason_code,'INVALID_POP')

    def test_undeclared_expression_rejected(self):
        plan=base();plan.steps.add(kind=a.SessionStep.ASSERT,assertion=variable('does_not_exist'))
        plan.steps.add(kind=a.SessionStep.CHECK)
        _,out=self.run_case(plan)
        self.assertEqual(out.reason_code,'UNKNOWN_VARIABLE')

    def test_status_count_mismatch_rejected(self):
        plan=base();plan.steps.add(kind=a.SessionStep.CHECK)
        if not self.reg:self.skipTest('optional Z3 unavailable')
        out=a.SessionResult.FromString(run_session_frame(wire(plan),self.reg,host_authorized=True,
                                                        status_runner=lambda *_: ['sat','unsat']))
        self.assertFalse(out.completed);self.assertEqual(out.reason_code,'INVALID_INCREMENTAL_STATUSES')

    def test_status_disagreement_is_not_proof(self):
        plan=base();plan.steps.add(kind=a.SessionStep.ASSERT,assertion=variable('x'))
        plan.steps.add(kind=a.SessionStep.CHECK)
        if not self.reg:self.skipTest('optional Z3 unavailable')
        out=a.SessionResult.FromString(run_session_frame(wire(plan),self.reg,host_authorized=True,
                                                        status_runner=lambda *_: ['unsat']))
        self.assertTrue(out.completed)
        self.assertEqual(out.checkpoints[0].backend_result.verdict,b.UNKNOWN)
        self.assertFalse(a.SessionReceipt.FromString(verify_session_frame(wire(plan),wire(out))).evidence_valid)

    def test_unknown_outcome_remains_unverified(self):
        plan=base();plan.steps.add(kind=a.SessionStep.CHECK)
        if not self.reg:self.skipTest('optional Z3 unavailable')
        out=a.SessionResult.FromString(run_session_frame(wire(plan),self.reg,host_authorized=True,
                                                        status_runner=lambda *_: ['unknown']))
        self.assertEqual(out.checkpoints[0].backend_result.verdict,b.UNKNOWN)
        self.assertFalse(a.SessionReceipt.FromString(verify_session_frame(wire(plan),wire(out))).evidence_valid)

    def test_assumption_sort_must_be_bool(self):
        plan=base(b.BV);plan.steps.add(kind=a.SessionStep.CHECK,assumptions=[variable('x')])
        _,out=self.run_case(plan)
        self.assertEqual(out.reason_code,'ASSERTION_MUST_BE_BOOLEAN')

    def test_no_arbitrary_backend_command(self):
        plan=base();plan.backend_id='../../bin/sh';plan.steps.add(kind=a.SessionStep.CHECK)
        _,out=self.run_case(plan)
        self.assertEqual(out.reason_code,'BACKEND_NOT_REGISTERED')

if __name__=='__main__':unittest.main()
