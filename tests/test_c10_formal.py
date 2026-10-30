"""Focused C10 P1 math/contract tests; no model or benchmark claims."""
import hashlib
import itertools
import random
import unittest

from cognitum.proto import formal_pb2 as p
from cognitum.formal_solver import (
    solve_frame, verify_frame, check_frame, prove_frame, verify_property_frame,
    validate_request, _difference_model_or_cycle, _check_cycle,
)


def wire(msg):
    return msg.SerializeToString(deterministic=True)


def run(req):
    a = wire(req)
    b = solve_frame(a)
    result = p.SolveResult.FromString(b)
    check = p.CheckResult.FromString(verify_frame(a,b))
    return result,check


def diff(req, left, right, bound):
    a=req.atoms.add();a.difference.left=left;a.difference.right=right;a.difference.bound=bound


def boolean(req, name):
    req.boolean_variables.append(name);req.atoms.add(boolean_name=name)


class SolverTests(unittest.TestCase):
    def test_empty_true(self):
        result,check=run(p.SolveRequest(schema_version=1))
        self.assertEqual(result.status,p.SAT);self.assertTrue(check.evidence_valid)

    def test_empty_clause_unsat(self):
        req=p.SolveRequest(schema_version=1);req.clauses.add()
        result,check=run(req);self.assertEqual(result.status,p.UNSAT)
        self.assertEqual(len(result.exhaustive_leaves),1);self.assertTrue(check.evidence_valid)

    def test_boolean_pure_sat(self):
        req=p.SolveRequest(schema_version=1);boolean(req,'a');boolean(req,'b')
        req.clauses.add(literals=[1,2]);req.clauses.add(literals=[-1])
        result,check=run(req);self.assertEqual(result.status,p.SAT)
        self.assertEqual(list(result.atom_values),[False,True]);self.assertTrue(check.evidence_valid)

    def test_boolean_unsat_and_certificate_tampering(self):
        req=p.SolveRequest(schema_version=1);boolean(req,'a');req.clauses.add(literals=[1]);req.clauses.add(literals=[-1])
        result,check=run(req);self.assertEqual(result.status,p.UNSAT);self.assertTrue(check.evidence_valid)
        result.exhaustive_leaves[0].false_clause=2
        self.assertFalse(p.CheckResult.FromString(verify_frame(wire(req),wire(result))).evidence_valid)

    def test_difference_sat_model_normalizes_zero(self):
        req=p.SolveRequest(schema_version=1,integer_variables=['x','y'])
        diff(req,'x','y',2);diff(req,'y','$ZERO',-4);diff(req,'$ZERO','x',6)
        req.clauses.add(literals=[1]);req.clauses.add(literals=[2]);req.clauses.add(literals=[3])
        result,check=run(req);self.assertEqual(result.status,p.SAT);self.assertTrue(check.evidence_valid)
        v={x.name:x.value for x in result.integer_values}
        self.assertLessEqual(v['x']-v['y'],2);self.assertLessEqual(v['y'],-4);self.assertGreaterEqual(v['x'],-6)

    def test_negative_theory_literal_strict_integer(self):
        req=p.SolveRequest(schema_version=1,integer_variables=['x']);diff(req,'x','$ZERO',1)
        req.clauses.add(literals=[-1]);res,ck=run(req)
        self.assertEqual(res.status,p.SAT);self.assertTrue(ck.evidence_valid)
        self.assertGreaterEqual(res.integer_values[0].value,2)

    def test_difference_negative_cycle_certificate(self):
        req=p.SolveRequest(schema_version=1,integer_variables=['x','y'])
        diff(req,'x','y',0);diff(req,'y','x',-1)
        req.clauses.add(literals=[1]);req.clauses.add(literals=[2]);res,ck=run(req)
        self.assertEqual(res.status,p.UNSAT);self.assertTrue(ck.evidence_valid)
        self.assertTrue(any(x.negative_cycle_atoms for x in res.exhaustive_leaves))
        leaf=next(x for x in res.exhaustive_leaves if x.negative_cycle_atoms)
        leaf.negative_cycle_atoms[0]=99
        self.assertFalse(p.CheckResult.FromString(verify_frame(wire(req),wire(res))).evidence_valid)

    def test_mixed_sat_chooses_boolean_alt(self):
        req=p.SolveRequest(schema_version=1,integer_variables=['x'])
        boolean(req,'override');diff(req,'x','$ZERO',0);diff(req,'$ZERO','x',-1)
        req.clauses.add(literals=[1,2]);req.clauses.add(literals=[3])
        res,ck=run(req);self.assertEqual(res.status,p.SAT);self.assertTrue(ck.evidence_valid)

    def test_unknown_budget_never_claims_unsat(self):
        req=p.SolveRequest(schema_version=1,max_assignments=1)
        boolean(req,'b');req.clauses.add(literals=[1]);res,ck=run(req)
        self.assertEqual(res.status,p.UNKNOWN);self.assertFalse(ck.evidence_valid)
        self.assertFalse(res.exhaustive_leaves)

    def test_wrong_hash_or_model_fails(self):
        req=p.SolveRequest(schema_version=1,integer_variables=['x'])
        diff(req,'x','$ZERO',-5);req.clauses.add(literals=[1]);res,ck=run(req);self.assertTrue(ck.evidence_valid)
        res.integer_values[0].value=0
        self.assertFalse(p.CheckResult.FromString(verify_frame(wire(req),wire(res))).evidence_valid)
        res,ck=run(req);res.request_sha256=b'fake'
        self.assertFalse(p.CheckResult.FromString(verify_frame(wire(req),wire(res))).evidence_valid)

    def test_disallow_semantic_and_host_authority_claims(self):
        req=p.SolveRequest(schema_version=1);r,_=run(req)
        r.host_approved=True
        self.assertFalse(p.CheckResult.FromString(verify_frame(wire(req),wire(r))).evidence_valid)
        r.host_approved=False;r.formalization_verified=True
        self.assertFalse(p.CheckResult.FromString(verify_frame(wire(req),wire(r))).evidence_valid)

    def test_boolean_duplicate_and_undeclared(self):
        req=p.SolveRequest(schema_version=1,boolean_variables=['x','x']);req.atoms.add(boolean_name='x')
        with self.assertRaises(ValueError):solve_frame(wire(req))
        req=p.SolveRequest(schema_version=1);req.atoms.add(boolean_name='x')
        with self.assertRaises(ValueError):solve_frame(wire(req))

    def test_bad_var_or_bound(self):
        req=p.SolveRequest(schema_version=1,integer_variables=['../etc']);diff(req,'../etc','$ZERO',1)
        with self.assertRaises(ValueError):solve_frame(wire(req))
        req=p.SolveRequest(schema_version=1,integer_variables=['x']);diff(req,'x','$ZERO',1_000_001)
        with self.assertRaises(ValueError):solve_frame(wire(req))
        req=p.SolveRequest(schema_version=1);req.clauses.add(literals=[1]);
        with self.assertRaises(ValueError):solve_frame(wire(req))

    def test_oversized_or_noncanonical_frames(self):
        req=p.SolveRequest(schema_version=1)
        with self.assertRaises(ValueError):solve_frame(wire(req)+b'\x78\x01')
        with self.assertRaises(ValueError):solve_frame(wire(req)+b'\x08\x01')
        with self.assertRaises(ValueError):solve_frame(b'\x08\x80')
        with self.assertRaises(ValueError):solve_frame(b'X'*9000)

    def test_self_difference_contradiction_and_integer_negation(self):
        req=p.SolveRequest(schema_version=1,integer_variables=['x'])
        diff(req,'x','x',-1);req.clauses.add(literals=[1])
        res,ck=run(req)
        self.assertEqual(res.status,p.UNSAT);self.assertTrue(ck.evidence_valid)
        self.assertEqual(list(res.exhaustive_leaves[1].negative_cycle_atoms),[1])
        req.clauses.clear();req.clauses.add(literals=[-1])
        res,ck=run(req)
        self.assertEqual(res.status,p.SAT);self.assertTrue(ck.evidence_valid)

    def test_unsat_missing_branch_or_wrong_cycle_order_fails(self):
        req=p.SolveRequest(schema_version=1,integer_variables=['x','y'])
        diff(req,'x','y',0);diff(req,'y','x',-1)
        req.clauses.add(literals=[1]);req.clauses.add(literals=[2])
        res,_=run(req)
        del res.exhaustive_leaves[-1]
        self.assertFalse(p.CheckResult.FromString(verify_frame(wire(req),wire(res))).evidence_valid)
        res,_=run(req)
        cycle=next(leaf for leaf in res.exhaustive_leaves if leaf.negative_cycle_atoms)
        cycle.negative_cycle_atoms.append(1)
        self.assertFalse(p.CheckResult.FromString(verify_frame(wire(req),wire(res))).evidence_valid)

    def test_unsupported_atom_budget_hard_reject(self):
        req=p.SolveRequest(schema_version=1)
        for j in range(11): boolean(req,'b'+str(j))
        with self.assertRaises(ValueError):solve_frame(wire(req))
        req=p.SolveRequest(schema_version=1,max_assignments=1025)
        with self.assertRaises(ValueError):solve_frame(wire(req))

    def test_verification_envelope(self):
        req=p.SolveRequest(schema_version=1);r,_=run(req)
        proof=p.CheckRequest(solve_request=wire(req),solve_result=wire(r))
        self.assertTrue(p.CheckResult.FromString(check_frame(wire(proof))).evidence_valid)

    def test_random_small_formula_against_brute_model(self):
        # Independent exact finite-model oracle: coefficients in [-2,2],
        # 2 variables. A feasible difference system has model in [-8,8].
        rng=random.Random(7031)
        for _ in range(160):
            req=p.SolveRequest(schema_version=1,integer_variables=['x','y'])
            n=rng.randrange(1,5)
            for j in range(n):
                left,right=rng.choice(['x','y','$ZERO']),rng.choice(['x','y','$ZERO'])
                diff(req,left,right,rng.randint(-2,2))
            for j in range(rng.randrange(0,5)):
                req.clauses.add(literals=[rng.choice([-1,1])*rng.randint(1,n) for _ in range(rng.randint(1,3))])
            result,check=run(req)
            self.assertIn(result.status,(p.SAT,p.UNSAT))
            self.assertTrue(check.evidence_valid)
            brute=False
            for mask in range(1<<n):
                if any(not any((bool(mask & (1<<(abs(lit)-1))) if lit>0 else not bool(mask & (1<<(abs(lit)-1)))) for lit in clause.literals) for clause in req.clauses):
                    continue
                for x,y in itertools.product(range(-8,9),repeat=2):
                    vals={'x':x,'y':y,'$ZERO':0}
                    if all(((vals[a.difference.left]-vals[a.difference.right] <= a.difference.bound) == bool(mask & (1<<i))) for i,a in enumerate(req.atoms)):
                        brute=True;break
                if brute:break
            self.assertEqual(result.status==p.SAT,brute,req)


class PropertyTests(unittest.TestCase):
    def test_proven_entailment(self):
        req=p.SolveRequest(schema_version=1,boolean_variables=['p'])
        req.atoms.add(boolean_name='p');req.clauses.add(literals=[1])
        prop=p.PropertyRequest(assumptions=req,required_literal=1)
        r=prove_frame(wire(prop));self.assertEqual(p.PropertyResult.FromString(r).verdict,p.PROVEN)
        self.assertTrue(p.CheckResult.FromString(verify_property_frame(wire(prop),r)).evidence_valid)

    def test_counterexample(self):
        req=p.SolveRequest(schema_version=1,boolean_variables=['p'])
        req.atoms.add(boolean_name='p')
        prop=p.PropertyRequest(assumptions=req,required_literal=1)
        r=prove_frame(wire(prop));self.assertEqual(p.PropertyResult.FromString(r).verdict,p.COUNTEREXAMPLE)
        self.assertTrue(p.CheckResult.FromString(verify_property_frame(wire(prop),r)).evidence_valid)

    def test_inconsistent_assumptions_not_genuine_proof(self):
        req=p.SolveRequest(schema_version=1,boolean_variables=['p'])
        req.atoms.add(boolean_name='p');req.clauses.add(literals=[1]);req.clauses.add(literals=[-1])
        prop=p.PropertyRequest(assumptions=req,required_literal=1)
        r=prove_frame(wire(prop));self.assertEqual(p.PropertyResult.FromString(r).verdict,p.INCONSISTENT_ASSUMPTIONS)
        self.assertTrue(p.CheckResult.FromString(verify_property_frame(wire(prop),r)).evidence_valid)

    def test_property_budget_unknown(self):
        req=p.SolveRequest(schema_version=1,boolean_variables=['p'],max_assignments=1)
        req.atoms.add(boolean_name='p');req.clauses.add(literals=[1]);prop=p.PropertyRequest(assumptions=req,required_literal=1)
        r=prove_frame(wire(prop));self.assertEqual(p.PropertyResult.FromString(r).verdict,p.INCONCLUSIVE)
        self.assertFalse(p.CheckResult.FromString(verify_property_frame(wire(prop),r)).evidence_valid)

    def test_exact_integer_theory_property(self):
        req=p.SolveRequest(schema_version=1,integer_variables=['x'])
        diff(req,'x','$ZERO',2);diff(req,'x','$ZERO',3)
        req.clauses.add(literals=[1]);prop=p.PropertyRequest(assumptions=req,required_literal=2)
        result=prove_frame(wire(prop))
        self.assertEqual(p.PropertyResult.FromString(result).verdict,p.PROVEN)
        self.assertTrue(p.CheckResult.FromString(verify_property_frame(wire(prop),result)).evidence_valid)
        prop.required_literal=-2
        result=prove_frame(wire(prop))
        self.assertEqual(p.PropertyResult.FromString(result).verdict,p.COUNTEREXAMPLE)
        self.assertTrue(p.CheckResult.FromString(verify_property_frame(wire(prop),result)).evidence_valid)

    def test_counterexample_valid_if_base_budget_is_unknown(self):
        req=p.SolveRequest(schema_version=1,boolean_variables=['p'],max_assignments=1)
        req.atoms.add(boolean_name='p');req.clauses.add(literals=[-1])
        prop=p.PropertyRequest(assumptions=req,required_literal=1)
        result=prove_frame(wire(prop))
        self.assertEqual(p.PropertyResult.FromString(result).verdict,p.COUNTEREXAMPLE)
        self.assertTrue(p.CheckResult.FromString(verify_property_frame(wire(prop),result)).evidence_valid)

    def test_property_claims_of_semantic_formalization_or_host_approval_fail(self):
        req=p.SolveRequest(schema_version=1,boolean_variables=['p'])
        req.atoms.add(boolean_name='p');req.clauses.add(literals=[1])
        prop=p.PropertyRequest(assumptions=req,required_literal=1)
        proof=p.PropertyResult.FromString(prove_frame(wire(prop)))
        proof.formalization_verified=True
        self.assertFalse(p.CheckResult.FromString(verify_property_frame(wire(prop),wire(proof))).evidence_valid)
        proof.formalization_verified=False;proof.host_approved=True
        self.assertFalse(p.CheckResult.FromString(verify_property_frame(wire(prop),wire(proof))).evidence_valid)

    def test_tampered_proof_denied(self):
        req=p.SolveRequest(schema_version=1,boolean_variables=['p']);req.atoms.add(boolean_name='p')
        prop=p.PropertyRequest(assumptions=req,required_literal=1);r=p.PropertyResult.FromString(prove_frame(wire(prop)))
        r.verdict=p.PROVEN
        self.assertFalse(p.CheckResult.FromString(verify_property_frame(wire(prop),wire(r))).evidence_valid)
        r=p.PropertyResult.FromString(prove_frame(wire(prop)));r.property_sha256=b'x'
        self.assertFalse(p.CheckResult.FromString(verify_property_frame(wire(prop),wire(r))).evidence_valid)

    def test_invalid_property_rejected(self):
        req=p.SolveRequest(schema_version=1,boolean_variables=['p']);req.atoms.add(boolean_name='p')
        with self.assertRaises(ValueError):prove_frame(wire(p.PropertyRequest(assumptions=req,required_literal=2)))

if __name__ == '__main__':unittest.main()
