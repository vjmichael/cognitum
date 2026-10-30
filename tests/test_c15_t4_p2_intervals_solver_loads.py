"""T4 P2 read-only adversarial interval, coupled-joint and load-envelope tests.

Direct SciPy and symbolic SymPy oracles are separately constructed, not called
from the implementation's formulas. Synthetic fixtures are not physical tests.
"""
import math
import random
import unittest

from cognitum.proto import spatial_functional_material_pb2 as b
from cognitum.proto import spatial_functional_material_p2_pb2 as p
from cognitum.spatial_functional_material import T4Rejected
from cognitum.spatial_functional_material_p2 import analyze, _sub, _multiply, I

E=b.T4_MEASUREMENT_ASSERTED


def q(value,unit, evidence=E):
    return b.T4Quantity(value=value,unit=unit,evidence=evidence,source_ref='fixture')


def iv(value,delta,unit, delta_unit=None, evidence=E):
    z=p.T4P2Interval()
    z.center.CopyFrom(q(value,unit,evidence))
    z.radius.CopyFrom(q(delta,delta_unit or unit,evidence))
    return z


def si(value,delta=0,evidence=E):
    return p.T4P2SIInterval(center_si=value,radius_si=delta,evidence=evidence,source_ref='fixture')


def request():
    r=p.T4P2ResearchRequest(schema_version=1,research_only=True)
    r.baseline.schema_version=1;r.baseline.graph_id='t4graph';r.baseline.conversation_id='t4convo'
    r.baseline.research_only=True
    for ident in ('bore','shaft','beam','arm','arm2'):
        r.baseline.parts.add(id=ident,kind='physical_part',evidence=E,source_ref='fixture')
    return r


def fit(r):
    f=r.fits.add(id='fit',bore_part_id='bore',shaft_part_id='shaft')
    f.bore_diameter.CopyFrom(iv(10.2,.02,b.T4_MILLIMETER))
    f.shaft_diameter.CopyFrom(iv(10,.02,b.T4_MILLIMETER))
    f.allowed_min_clearance.CopyFrom(iv(.1,0,b.T4_MILLIMETER))
    f.allowed_max_clearance.CopyFrom(iv(.3,0,b.T4_MILLIMETER))
    return f


def joints(r,force=False):
    for i,part in enumerate(('arm','arm2'),start=1):
        j=r.baseline.joints.add(id=f'j{i}',parent_part_id='beam',child_part_id=part,kind=b.T4_PRISMATIC)
        j.lower_limit.CopyFrom(q(-1,b.T4_METER))
        j.upper_limit.CopyFrom(q(1,b.T4_METER))
        j.candidate_position.CopyFrom(q(.4 if i==1 else .5,b.T4_METER))
    a=r.assemblies.add(id='coupling',joint_check_ids=['j1','j2'],enforce_candidate_positions=force)
    c=a.constraints.add(id='sum')
    c.terms.add(joint_check_id='j1',coefficient=1)
    c.terms.add(joint_check_id='j2',coefficient=1)
    c.lower.CopyFrom(iv(-.01,0,b.T4_METER))
    c.upper.CopyFrom(iv(.01,0,b.T4_METER))
    return a


def loads(r):
    x=r.loads.add(id='loads',part_id='beam',safety_factor=1.5)
    x.axial_area.CopyFrom(iv(100,2,b.T4_SQUARE_MILLIMETER))
    x.shear_area.CopyFrom(iv(80,2,b.T4_SQUARE_MILLIMETER))
    x.section_modulus.CopyFrom(si(1000e-9,20e-9))  # 1000 mm^3
    x.allowable_normal_stress.CopyFrom(iv(200,5,b.T4_MEGAPASCAL))
    x.allowable_shear_stress.CopyFrom(iv(100,5,b.T4_MEGAPASCAL))
    x.compression_buckling_limit.CopyFrom(iv(10_000,100,b.T4_NEWTON))
    for ident,axial,shear,moment in [('case1',1000,100,5),('case2',-900,250,4)]:
        c=x.cases.add(id=ident)
        c.axial_force.CopyFrom(iv(axial,20,b.T4_NEWTON))
        c.shear_force.CopyFrom(iv(shear,10,b.T4_NEWTON))
        c.bending_moment.CopyFrom(si(moment,.1))
    return x


class T4P2Tests(unittest.TestCase):
    def find(self,r): return analyze(r).findings[0]
    def reject(self,r,code):
        with self.assertRaisesRegex(T4Rejected,code): analyze(r)

    def test_tolerance_mixed_units_and_proof(self):
        r=request();f=fit(r)
        f.shaft_diameter.CopyFrom(iv(.010,.00002,b.T4_METER))
        result=analyze(r)
        self.assertEqual(result.findings[0].status,b.T4_CONSISTENT_WITH_CLAIMS)
        self.assertTrue(result.findings[0].robust_for_claimed_intervals)
        self.assertAlmostEqual(result.findings[0].computed_min_si,.00016)
        self.assertAlmostEqual(result.findings[0].computed_max_si,.00024)
        self.assertFalse(result.physical_validity_verified)
        self.assertFalse(result.grants_authority)
        self.assertEqual(len(result.request_sha256),32)

    def test_uncertainty_overlap_must_abstain(self):
        r=request();f=fit(r)
        f.shaft_diameter.CopyFrom(iv(10,.10,b.T4_MILLIMETER))
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)

    def test_rejection_even_with_uncertainty(self):
        r=request();f=fit(r)
        f.shaft_diameter.CopyFrom(iv(12,.01,b.T4_MILLIMETER))
        self.assertEqual(self.find(r).status,b.T4_CONTRADICTS_CLAIMS)

    def test_boundary_only_undetermined(self):
        r=request();f=fit(r)
        f.shaft_diameter.CopyFrom(iv(10.1,0,b.T4_MILLIMETER))
        f.bore_diameter.CopyFrom(iv(10.2,0,b.T4_MILLIMETER))
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)

    def test_declared_thermal_missing_must_abstain(self):
        r=request();f=fit(r);f.thermal_exposure_declared=True
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)
        self.assertIn('THERMAL_EVIDENCE_MISSING',self.find(r).reasons)

    def test_thermal_growth_calculation(self):
        r=request();f=fit(r);f.thermal_exposure_declared=True
        f.thermal_range.CopyFrom(p.T4P2ThermalRange(
            bore_alpha_min_per_kelvin=1e-5,bore_alpha_max_per_kelvin=1e-5,
            shaft_alpha_min_per_kelvin=2e-5,shaft_alpha_max_per_kelvin=2e-5,
            delta_temperature_min_kelvin=100,delta_temperature_max_kelvin=100,
            evidence=E,source_ref='thermal_catalog'))
        o=self.find(r)
        self.assertEqual(o.status,b.T4_CONSISTENT_WITH_CLAIMS)
        self.assertIn('thermal_catalog',o.source_refs)
        self.assertAlmostEqual(o.computed_min_si, ((10.2-.02)*1.001-(10+.02)*1.002)*1e-3,places=10)

    def test_thermal_alpha_variation_can_remove_fit(self):
        r=request();f=fit(r);f.thermal_exposure_declared=True
        f.thermal_range.CopyFrom(p.T4P2ThermalRange(
            bore_alpha_min_per_kelvin=0,bore_alpha_max_per_kelvin=0,
            shaft_alpha_min_per_kelvin=.001,shaft_alpha_max_per_kelvin=.001,
            delta_temperature_min_kelvin=200,delta_temperature_max_kelvin=200,
            evidence=b.T4_HYPOTHETICAL,source_ref='thermal_hyp'))
        o=self.find(r)
        self.assertEqual(o.status,b.T4_CONTRADICTS_CLAIMS)
        self.assertIn('PROVISIONAL_OR_HYPOTHETICAL_EVIDENCE',o.reasons)

    def test_wrong_dimension_and_negative_uncertainty(self):
        r=request();f=fit(r)
        f.shaft_diameter.radius.CopyFrom(q(1,b.T4_NEWTON))
        self.reject(r,'DIMENSION_MISMATCH')
        f.shaft_diameter.radius.CopyFrom(q(-1,b.T4_MILLIMETER))
        self.reject(r,'NEGATIVE_UNCERTAINTY_RADIUS')

    def test_inf_nan_and_abusive_thermal_input(self):
        r=request();f=fit(r)
        f.shaft_diameter.radius.value=float('inf')
        self.reject(r,'NONFINITE_QUANTITY')
        f.shaft_diameter.radius.value=0
        f.thermal_exposure_declared=True
        f.thermal_range.CopyFrom(p.T4P2ThermalRange(
            bore_alpha_min_per_kelvin=.2,bore_alpha_max_per_kelvin=.3,
            shaft_alpha_min_per_kelvin=0,shaft_alpha_max_per_kelvin=0,
            delta_temperature_min_kelvin=0,delta_temperature_max_kelvin=100,
            evidence=E,source_ref='thermal'))
        self.reject(r,'THERMAL_RESOURCE_LIMIT')

    def test_no_thermal_undeclared_data(self):
        r=request();f=fit(r);f.thermal_range.evidence=E
        self.reject(r,'UNDECLARED_THERMAL_INPUT')

    def test_missing_tolerance_is_unknown(self):
        r=request();f=fit(r);f.allowed_max_clearance.ClearField('radius')
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)

    def test_cross_joint_feasible_by_scipy(self):
        r=request();joints(r)
        o=self.find(r)
        self.assertEqual(o.status,b.T4_CONSISTENT_WITH_CLAIMS)
        self.assertIn('LINEAR_FEASIBILITY_ONLY_NOT_KINEMATIC_CERTIFICATION',o.reasons)

    def test_cross_joint_infeasible_proof(self):
        r=request();a=joints(r)
        r.baseline.joints[0].lower_limit.value=.8
        r.baseline.joints[1].lower_limit.value=.8
        self.assertEqual(self.find(r).status,b.T4_CONTRADICTS_CLAIMS)

    def test_cross_joint_candidate_violation(self):
        r=request();joints(r,True)
        self.assertEqual(self.find(r).status,b.T4_CONTRADICTS_CLAIMS)

    def test_joint_uncertain_coupling_is_existential_not_robust(self):
        r=request();a=joints(r)
        a.constraints[0].upper.radius.value=.1
        o=self.find(r)
        self.assertEqual(o.status,b.T4_UNDETERMINED)
        self.assertFalse(o.robust_for_claimed_intervals)
        self.assertIn('EXISTENTIAL_ONLY_UNCERTAIN_ASSEMBLY',o.reasons)

    def test_joint_dimension_mixing_rejected(self):
        r=request();joints(r)
        j=r.baseline.joints[1]
        j.kind=b.T4_REVOLUTE
        j.lower_limit.CopyFrom(q(-1,b.T4_RADIAN))
        j.upper_limit.CopyFrom(q(1,b.T4_RADIAN))
        j.candidate_position.CopyFrom(q(.5,b.T4_RADIAN))
        self.reject(r,'MIXED_JOINT_DIMENSIONS')

    def test_joint_invalid_coefficients_and_missing(self):
        r=request();a=joints(r)
        a.constraints[0].terms[0].coefficient=math.nan
        self.reject(r,'INVALID_LINEAR_TERM')
        a.constraints[0].terms[0].coefficient=1
        a.constraints[0].lower.ClearField('radius')
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)

    def test_near_infeasible_solver_must_not_produce_positive(self):
        r=request();a=joints(r)
        for j in r.baseline.joints:
            j.lower_limit.value=0
            j.upper_limit.value=0
            j.candidate_position.value=0
        a.constraints[0].lower.CopyFrom(iv(1e-12,0,b.T4_METER))
        a.constraints[0].upper.CopyFrom(iv(2e-12,0,b.T4_METER))
        self.assertNotEqual(self.find(r).status,b.T4_CONSISTENT_WITH_CLAIMS)

    def test_solver_no_constraints_abstains(self):
        r=request();a=joints(r);a.constraints.clear()
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)

    def test_assembly_parent_scope_cannot_be_forged(self):
        r=request();a=joints(r)
        a.joint_check_ids[0]='foreign_joint'
        self.reject(r,'UNKNOWN_OR_DUPLICATE_JOINT')

    def test_joint_provisional_is_undetermined(self):
        r=request();joints(r)
        r.baseline.parts[2].evidence=b.T4_HYPOTHETICAL
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)

    def test_joint_solver_availability_is_failclosed(self):
        # Constraint-free graph is insufficient evidence.
        r=request();a=joints(r)
        a.constraints.clear()
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)

    def test_multi_case_load_passes_conditionally(self):
        r=request();loads(r)
        o=self.find(r)
        self.assertEqual(o.status,b.T4_CONSISTENT_WITH_CLAIMS)
        self.assertTrue(o.robust_for_claimed_intervals)
        self.assertGreater(o.computed_max_si,0)
        self.assertLess(o.computed_max_si,1)

    def test_missing_buckling_is_unknown_not_pass(self):
        r=request();x=loads(r);x.ClearField('compression_buckling_limit')
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)
        self.assertIn('MISSING_BUCKLING_FATIGUE_OR_LOAD_CASE_EVIDENCE',self.find(r).reasons)

    def test_buckling_failure_detected(self):
        r=request();x=loads(r)
        x.compression_buckling_limit.CopyFrom(iv(800,0,b.T4_NEWTON))
        self.assertEqual(self.find(r).status,b.T4_CONTRADICTS_CLAIMS)

    def test_bending_overload_detected(self):
        r=request();x=loads(r)
        x.cases[0].bending_moment.CopyFrom(si(500,.01))
        self.assertEqual(self.find(r).status,b.T4_CONTRADICTS_CLAIMS)

    def test_shear_overload_detected(self):
        r=request();x=loads(r)
        x.cases[0].shear_force.CopyFrom(iv(100_000,0,b.T4_NEWTON))
        self.assertEqual(self.find(r).status,b.T4_CONTRADICTS_CLAIMS)

    def test_cyclic_missing_fatigue_is_unknown(self):
        r=request();x=loads(r);x.cases[0].cyclic=True;x.cases[0].applied_cycles=1000
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)

    def test_cyclic_overrun_rejected(self):
        r=request();x=loads(r);x.cases[0].cyclic=True;x.cases[0].applied_cycles=1000
        x.fatigue_allowable_cycles=500;x.fatigue_evidence=E;x.fatigue_source_ref='fatigue_claim'
        self.assertEqual(self.find(r).status,b.T4_CONTRADICTS_CLAIMS)

    def test_cyclic_with_bound_is_conditional_only(self):
        r=request();x=loads(r);x.cases[0].cyclic=True;x.cases[0].applied_cycles=1000
        x.fatigue_allowable_cycles=3000;x.fatigue_evidence=E;x.fatigue_source_ref='fatigue_claim'
        o=self.find(r)
        self.assertEqual(o.status,b.T4_CONSISTENT_WITH_CLAIMS)
        self.assertFalse(analyze(r).physical_validity_verified)

    def test_cyclic_claim_hypothetical_must_abstain(self):
        r=request();x=loads(r);x.cases[0].cyclic=True;x.cases[0].applied_cycles=100
        x.fatigue_allowable_cycles=3000;x.fatigue_evidence=b.T4_HYPOTHETICAL;x.fatigue_source_ref='hyp'
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)

    def test_uncertainty_interval_straddles_allowance(self):
        r=request();x=loads(r)
        x.cases[0].bending_moment.CopyFrom(si(110,20))
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)

    def test_unknown_required_load_data_abstains(self):
        r=request();x=loads(r);x.cases[0].ClearField('bending_moment')
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)

    def test_nonpositive_interval_denominator_abstains(self):
        r=request();x=loads(r);x.axial_area.radius.value=200
        self.assertEqual(self.find(r).status,b.T4_UNDETERMINED)

    def test_negative_radius_rejected(self):
        r=request();x=loads(r);x.section_modulus.radius_si=-1
        self.reject(r,'NEGATIVE_UNCERTAINTY_RADIUS')

    def test_resource_gates(self):
        r=request()
        for i in range(65):r.fits.add(id=f'f{i}')
        self.reject(r,'RESOURCE_LIMIT')
        r=request();x=loads(r)
        for i in range(16):x.cases.add(id=f'extra{i}')
        self.reject(r,'INVALID_LOAD_ENVELOPE')

    def test_deterministic_and_caller_id(self):
        r=request();fit(r);joints(r);loads(r)
        a=analyze(r);bb=analyze(r)
        self.assertEqual(a.SerializeToString(deterministic=True),bb.SerializeToString(deterministic=True))
        self.assertEqual([x.id for x in a.findings],['fit','coupling','loads'])
        self.assertEqual(a.graph_id,'t4graph')

    def test_no_authority_unknown_fields(self):
        r=request();fit(r);r.grants_authority=True
        self.reject(r,'INVALID_RESEARCH_CONTRACT')
        r.grants_authority=False;r.baseline.grants_authority=True
        self.reject(r,'INVALID_RESEARCH_CONTRACT')

    def test_independent_sympy_interval_oracle(self):
        import sympy as S
        rng=random.Random(771)
        for _ in range(70):
            c1=rng.uniform(5,40);r1=rng.uniform(0,.5)
            c2=rng.uniform(5,40);r2=rng.uniform(0,.5)
            u=I(c1-r1,c1+r1,False,frozenset())
            v=I(c2-r2,c2+r2,False,frozenset())
            observed=_sub(u,v)
            # SymPy symbolic minimization over the box: endpoints exact for subtraction.
            x,y=S.symbols('x y',real=True)
            expr=x-y
            extreme=[float(expr.subs({x:xx,y:yy})) for xx in (u.lo,u.hi) for yy in (v.lo,v.hi)]
            self.assertAlmostEqual(observed.lo,min(extreme),places=11)
            self.assertAlmostEqual(observed.hi,max(extreme),places=11)

    def test_independent_scipy_linear_feasibility_oracle(self):
        from scipy.optimize import linprog
        rng=random.Random(772)
        for _ in range(65):
            r=request();a=joints(r)
            l1=rng.uniform(-.9,.8);l2=rng.uniform(-.9,.8)
            u1=l1+rng.uniform(.01,.2);u2=l2+rng.uniform(.01,.2)
            r.baseline.joints[0].lower_limit.value=l1;r.baseline.joints[0].upper_limit.value=u1
            r.baseline.joints[1].lower_limit.value=l2;r.baseline.joints[1].upper_limit.value=u2
            lower=rng.uniform(-.5,.5);upper=lower+rng.uniform(.01,.3)
            a.constraints[0].lower.center.value=lower
            a.constraints[0].upper.center.value=upper
            truth=linprog([0,0],A_ub=[[1,1],[-1,-1]],b_ub=[upper,-lower],bounds=[(l1,u1),(l2,u2)],method='highs')
            observed=analyze(r).findings[0].status
            if truth.status==0:
                self.assertIn(observed,(b.T4_CONSISTENT_WITH_CLAIMS,b.T4_UNDETERMINED))
            elif truth.status==2:
                self.assertIn(observed,(b.T4_CONTRADICTS_CLAIMS,b.T4_UNDETERMINED))
            else:
                self.assertEqual(observed,b.T4_UNDETERMINED)

    def test_worst_case_load_sympy_oracle(self):
        import sympy as S
        r=request();x=loads(r)
        x.cases[0].axial_force.CopyFrom(iv(1000,0,b.T4_NEWTON))
        x.cases[0].bending_moment.CopyFrom(si(5,0))
        # Exact rational oracle, independent of T4 formulas' Python implementation.
        f,Ssec,area=S.symbols('F Z A',positive=True)
        expr=f/area+S.Rational(5)/Ssec
        truth=expr.subs({f:1000,area:S.Rational(100,10**6),Ssec:S.Rational(1000,10**9)})
        self.assertEqual(truth,S.Rational(15_000_000,1))
        self.assertLess(self.find(r).computed_max_si,1)


if __name__=='__main__': unittest.main()
