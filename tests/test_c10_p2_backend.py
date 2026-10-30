"""Focused C10 P2 correctness/security tests, never a performance benchmark."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from fractions import Fraction

from cognitum.proto import formal_backend_pb2 as p
from cognitum.formal_backend import (
 ApprovedBackend, SolverRegistry, compile_run, parse_response, verify_backend_frame,
 UnsupportedFormula, parse_exact, eval_expr,
)

def wire(x):return x.SerializeToString(deterministic=True)

def v(name):return p.Expr(variable=name)
def i(n):return p.Expr(integer=p.IntegerLiteral(decimal=str(n)))
def real(a,b=1):return p.Expr(rational=p.RationalLiteral(numerator=str(a),denominator=str(b)))
def bv(n,width):return p.Expr(bitvector=p.BitVectorLiteral(value=n,width=width))
def op(code,*xs):return p.Expr(application=p.Application(op=code,args=xs))
def request(*assertions,backend='z3-lib',variables=()):
    q=p.BackendRun(schema_version=1,backend_id=backend,timeout_ms=3000,trace_id='test:c10p2')
    for name,sort,width in variables:q.variables.add(name=name,sort=sort,width=width)
    for a in assertions:q.assertions.add().CopyFrom(a)
    return q

class P2BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates=[Path('/lib/x86_64-linux-gnu/libz3.so.4'),Path('/usr/lib/x86_64-linux-gnu/libz3.so.4')]
        cls.lib=next((x for x in candidates if x.is_file()),None)
        if cls.lib:
            cls.approved=ApprovedBackend('z3-lib','z3-lib',str(cls.lib),hashlib.sha256(cls.lib.read_bytes()).hexdigest())

    def test_no_host_authority(self):
        q=request(p.Expr(boolean=True))
        r=p.BackendResult.FromString(SolverRegistry().run_frame(wire(q)))
        self.assertEqual(r.verdict,p.REJECTED)
        self.assertEqual(r.reason_code,'HOST_AUTHORIZATION_REQUIRED')

    def test_no_unregistered_backend_even_with_authority(self):
        q=request(p.Expr(boolean=True));r=p.BackendResult.FromString(SolverRegistry().run_frame(wire(q),host_authorized=True))
        self.assertEqual(r.verdict,p.REJECTED)

    def test_disabled_registry_never_dispatches(self):
        q=request(p.Expr(boolean=True));reg=SolverRegistry();reg.disable()
        r=p.BackendResult.FromString(reg.run_frame(wire(q),host_authorized=True))
        self.assertEqual(r.reason_code,'REGISTRY_DISABLED')

    def test_invalid_approved_file(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'z3';f.write_text('fake backend')
            good=ApprovedBackend('z3-lib','z3-lib',str(f),hashlib.sha256(f.read_bytes()).hexdigest());good.validate()
            f.write_text('changed backend')
            with self.assertRaisesRegex(ValueError,'BACKEND_BINARY_CHANGED'):good.validate()

    def test_unsupported_binary_name_or_kind(self):
        if self.lib is None:self.skipTest('local Z3 library unavailable')
        a=self.approved
        with self.assertRaises(ValueError):ApprovedBackend('shell','shell',a.absolute_path,a.sha256).validate()

    def test_reject_smt_injection_in_variable(self):
        q=request(p.Expr(boolean=True),variables=[('x) (exit)',p.INT,0)])
        with self.assertRaises(ValueError):compile_run(q)

    def test_reject_undeclared_name_and_mistyped_boolean(self):
        with self.assertRaises(ValueError):compile_run(request(v('missing')))
        with self.assertRaises(ValueError):compile_run(request(i(2)))
        with self.assertRaises(ValueError):compile_run(request(op(p.AND,i(2),p.Expr(boolean=True))))

    def test_reject_wrong_arity_unknown_operator_and_depth(self):
        with self.assertRaises(ValueError):compile_run(request(op(p.NOT,p.Expr(boolean=True),p.Expr(boolean=False))))
        with self.assertRaises(UnsupportedFormula):compile_run(request(op(p.OP_UNSPECIFIED,p.Expr(boolean=True))))
        expr=p.Expr(boolean=True)
        for _ in range(25):expr=op(p.NOT,expr)
        with self.assertRaises(ValueError):compile_run(request(expr))

    def test_reject_noncanonical_literals(self):
        with self.assertRaises(ValueError):compile_run(request(op(p.EQ,i('01'),i(1))))
        with self.assertRaises(ValueError):compile_run(request(op(p.EQ,real(1,0),real(1,2))))
        with self.assertRaises(ValueError):compile_run(request(op(p.EQ,bv(32,5),bv(1,5))))

    def test_strict_solver_response_and_model_verification(self):
        q=request(op(p.GT,v('x'),i(1)),variables=[('x',p.INT,0)])
        _,symbols,trees=compile_run(q)
        self.assertEqual(parse_response('sat\n((x 2))\n',symbols,trees)[0],'sat')
        for bad in ['sat\n((x 1))\n','sat\n((x 2) (x 9))\n','sat\n((y 2))\n','sat\n((x (/ 3 2)))','sat\n((x 2)) (exit)','sat\n((x 2))\nunsat']:
            with self.subTest(bad=bad),self.assertRaises(ValueError):parse_response(bad,symbols,trees)

    def test_unsat_never_is_a_verified_proof(self):
        q=request(p.Expr(boolean=True))
        if not self.lib:self.skipTest('local Z3 unavailable')
        reg=SolverRegistry((self.approved,))
        res=p.BackendResult.FromString(reg.run_frame(wire(q),host_authorized=True,runner=lambda *_:'unsat'))
        self.assertEqual(res.verdict,p.UNSAT)
        self.assertEqual(res.verification,p.UNSAT_NOT_PROVEN)
        receipt=p.VerificationReceipt.FromString(verify_backend_frame(wire(q),wire(res)))
        self.assertFalse(receipt.evidence_valid)

    def test_malicious_sat_claim_rejected(self):
        if not self.lib:self.skipTest('local Z3 unavailable')
        q=request(op(p.GT,v('x'),i(9)),variables=[('x',p.INT,0)])
        reg=SolverRegistry((self.approved,))
        r=p.BackendResult.FromString(reg.run_frame(wire(q),host_authorized=True,runner=lambda *_:'sat\n((x 0))\n'))
        self.assertEqual(r.verdict,p.ERROR)

    def test_receipt_tampering_and_wrong_request(self):
        if not self.lib:self.skipTest('local Z3 unavailable')
        q=request(op(p.GT,v('x'),i(3)),variables=[('x',p.INT,0)])
        reg=SolverRegistry((self.approved,))
        raw=reg.run_frame(wire(q),host_authorized=True,runner=lambda *_:'sat\n((x 4))\n')
        good=p.VerificationReceipt.FromString(verify_backend_frame(wire(q),raw))
        self.assertTrue(good.evidence_valid)
        fake=p.BackendResult.FromString(raw);fake.model[0].exact_value='1'
        self.assertFalse(p.VerificationReceipt.FromString(verify_backend_frame(wire(q),wire(fake))).evidence_valid)
        fake=p.BackendResult.FromString(raw);fake.host_approved=True
        self.assertFalse(p.VerificationReceipt.FromString(verify_backend_frame(wire(q),wire(fake))).evidence_valid)
        another=request(op(p.GT,v('x'),i(8)),variables=[('x',p.INT,0)])
        self.assertFalse(p.VerificationReceipt.FromString(verify_backend_frame(wire(another),raw)).evidence_valid)

    def test_unknown_and_timeout_distinct_from_proof(self):
        if not self.lib:self.skipTest('local Z3 unavailable')
        q=request(p.Expr(boolean=True));reg=SolverRegistry((self.approved,))
        res=p.BackendResult.FromString(reg.run_frame(wire(q),host_authorized=True,runner=lambda *_:'unknown'))
        self.assertEqual(res.verdict,p.UNKNOWN)
        self.assertFalse(p.VerificationReceipt.FromString(verify_backend_frame(wire(q),wire(res))).evidence_valid)

    def test_exact_rational_and_bv_parser(self):
        self.assertEqual(parse_exact(['/', '1', '3'],p.REAL,0),Fraction(1,3))
        self.assertEqual(parse_exact(['-',['/','3','4']],p.REAL,0),Fraction(-3,4))
        self.assertEqual(parse_exact('#x0f',p.BV,8),15)
        self.assertEqual(parse_exact(['_','bv5','7'],p.BV,7),5)
        with self.assertRaises(ValueError):parse_exact('#b101',p.BV,4)

    def test_actual_z3_sat_integer(self):
        if not self.lib:self.skipTest('local Z3 library unavailable')
        q=request(op(p.GE,v('x'),i(7)),variables=[('x',p.INT,0)])
        reg=SolverRegistry((self.approved,))
        output=reg.run_frame(wire(q),host_authorized=True)
        r=p.BackendResult.FromString(output)
        self.assertEqual(r.verdict,p.SAT,r.reason_code)
        self.assertEqual(r.verification,p.SAT_WITNESS_CHECKED)
        self.assertTrue(p.VerificationReceipt.FromString(verify_backend_frame(wire(q),output)).evidence_valid)

    def test_actual_z3_unsat(self):
        if not self.lib:self.skipTest('local Z3 library unavailable')
        q=request(op(p.GE,v('x'),i(8)),op(p.LE,v('x'),i(1)),variables=[('x',p.INT,0)])
        output=SolverRegistry((self.approved,)).run_frame(wire(q),host_authorized=True)
        r=p.BackendResult.FromString(output)
        self.assertEqual(r.verdict,p.UNSAT,r.reason_code)
        self.assertEqual(r.verification,p.UNSAT_NOT_PROVEN)
        self.assertFalse(p.VerificationReceipt.FromString(verify_backend_frame(wire(q),output)).evidence_valid)

    def test_actual_z3_rational_and_bv(self):
        if not self.lib:self.skipTest('local Z3 library unavailable')
        q=request(op(p.GT,v('r'),real(1,3)),variables=[('r',p.REAL,0)])
        output=SolverRegistry((self.approved,)).run_frame(wire(q),host_authorized=True)
        r=p.BackendResult.FromString(output)
        self.assertEqual(r.verdict,p.SAT,r.reason_code)
        self.assertTrue(p.VerificationReceipt.FromString(verify_backend_frame(wire(q),output)).evidence_valid)
        q=request(op(p.BVULT,v('bits'),bv(3,8)),variables=[('bits',p.BV,8)])
        output=SolverRegistry((self.approved,)).run_frame(wire(q),host_authorized=True)
        r=p.BackendResult.FromString(output)
        self.assertEqual(r.verdict,p.SAT,r.reason_code)
        self.assertTrue(p.VerificationReceipt.FromString(verify_backend_frame(wire(q),output)).evidence_valid)

if __name__=='__main__':unittest.main()
