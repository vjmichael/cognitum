"""C15 T4 P1 bounded research-only conditional engineering constraints."""
import math
import unittest
from google.protobuf.internal.encoder import _VarintBytes
from cognitum.proto import spatial_functional_material_pb2 as pb
from cognitum.spatial_functional_material import analyze, T4Rejected

E = pb.T4_MEASUREMENT_ASSERTED


def q(value, unit, evidence=E, source_ref="source1"):
    return pb.T4Quantity(value=value, unit=unit, evidence=evidence, source_ref=source_ref)


def req():
    r = pb.T4ResearchRequest(schema_version=1, graph_id="graph1", conversation_id="conversation1", research_only=True)
    for ident in ("shaft", "bore", "beam", "arm"):
        r.parts.add(id=ident, kind="test_part", evidence=E, source_ref="source1")
    return r


def fit(r):
    f = r.fits.add(id="fit1", bore_part_id="bore", shaft_part_id="shaft")
    f.bore_diameter.CopyFrom(q(10.2, pb.T4_MILLIMETER))
    f.shaft_diameter.CopyFrom(q(.010, pb.T4_METER))
    f.minimum_clearance.CopyFrom(q(.1, pb.T4_MILLIMETER))
    f.maximum_clearance.CopyFrom(q(.3, pb.T4_MILLIMETER))
    return f


def joint(r, kind=pb.T4_REVOLUTE):
    j = r.joints.add(id="joint1", parent_part_id="beam", child_part_id="arm", kind=kind)
    j.lower_limit.CopyFrom(q(-90, pb.T4_DEGREE))
    j.upper_limit.CopyFrom(q(90, pb.T4_DEGREE))
    j.candidate_position.CopyFrom(q(45, pb.T4_DEGREE))
    return j


def stress(r):
    s = r.stresses.add(id="stress1", part_id="beam", safety_factor=2)
    s.applied_force.CopyFrom(q(1000, pb.T4_NEWTON))
    s.cross_section_area.CopyFrom(q(100, pb.T4_SQUARE_MILLIMETER))
    s.allowable_stress.CopyFrom(q(100, pb.T4_MEGAPASCAL))
    return s


def deflection(r):
    d = r.deflections.add(id="deflect1", part_id="beam")
    d.applied_force.CopyFrom(q(10, pb.T4_NEWTON))
    d.linear_stiffness.CopyFrom(q(10, pb.T4_NEWTON_PER_MILLIMETER))
    d.maximum_deflection.CopyFrom(q(2, pb.T4_MILLIMETER))
    return d


class T4FunctionalMaterialTests(unittest.TestCase):
    def assert_reject(self, r, code):
        with self.assertRaisesRegex(T4Rejected, code): analyze(r)

    def test_fit_units_and_sources(self):
        r = req();fit(r)
        out = analyze(r)
        self.assertEqual(out.findings[0].status, pb.T4_CONSISTENT_WITH_CLAIMS)
        self.assertAlmostEqual(out.findings[0].computed_si, .0002)
        self.assertEqual(list(out.findings[0].source_refs), ["source1"])
        self.assertFalse(out.physical_validity_verified)
        self.assertFalse(out.grants_authority)
        self.assertEqual(len(out.request_sha256), 32)

    def test_fit_interference_contradiction(self):
        r = req();f=fit(r);f.shaft_diameter.CopyFrom(q(11, pb.T4_MILLIMETER))
        self.assertEqual(analyze(r).findings[0].status, pb.T4_CONTRADICTS_CLAIMS)

    def test_fit_oversize_and_underfill(self):
        for diameter in (9, 10.15):
            with self.subTest(diameter=diameter):
                r=req();f=fit(r);f.shaft_diameter.CopyFrom(q(diameter, pb.T4_MILLIMETER))
                self.assertEqual(analyze(r).findings[0].status, pb.T4_CONTRADICTS_CLAIMS)

    def test_fit_without_tolerance_not_proved(self):
        r=req();f=fit(r);f.ClearField("maximum_clearance")
        self.assertEqual(analyze(r).findings[0].status, pb.T4_UNDETERMINED)

    def test_fit_near_boundary_unknown(self):
        r=req();f=fit(r);f.shaft_diameter.CopyFrom(q(10.1, pb.T4_MILLIMETER))
        self.assertEqual(analyze(r).findings[0].status, pb.T4_UNDETERMINED)

    def test_reversed_fit_bounds(self):
        r=req();f=fit(r);f.minimum_clearance.CopyFrom(q(.4, pb.T4_MILLIMETER))
        self.assertIn("REVERSED_CLEARANCE_INTERVAL",analyze(r).findings[0].reasons)

    def test_revolute_degrees_to_radians(self):
        r=req();joint(r)
        o=analyze(r).findings[0]
        self.assertEqual(o.status,pb.T4_CONSISTENT_WITH_CLAIMS)
        self.assertAlmostEqual(o.computed_si, math.pi/4)

    def test_revolute_outside_limit(self):
        r=req();j=joint(r);j.candidate_position.CopyFrom(q(180,pb.T4_DEGREE))
        self.assertEqual(analyze(r).findings[0].status,pb.T4_CONTRADICTS_CLAIMS)

    def test_prismatic_requires_length(self):
        r=req();j=joint(r,pb.T4_PRISMATIC)
        self.assert_reject(r,"DIMENSION_MISMATCH")
        j.lower_limit.CopyFrom(q(-1,pb.T4_METER))
        j.upper_limit.CopyFrom(q(1,pb.T4_METER))
        j.candidate_position.CopyFrom(q(0,pb.T4_METER))
        self.assertEqual(analyze(r).findings[0].status,pb.T4_CONSISTENT_WITH_CLAIMS)

    def test_fixed_zero(self):
        r=req();j=joint(r,pb.T4_FIXED)
        for field in ("lower_limit","upper_limit","candidate_position"):
            getattr(j, field).CopyFrom(q(0,pb.T4_METER))
        self.assertEqual(analyze(r).findings[0].status,pb.T4_CONSISTENT_WITH_CLAIMS)
        j.candidate_position.CopyFrom(q(.1,pb.T4_METER))
        self.assertEqual(analyze(r).findings[0].status,pb.T4_CONTRADICTS_CLAIMS)

    def test_stress_with_factor_two(self):
        r=req();stress(r)
        o=analyze(r).findings[0]
        self.assertEqual(o.status,pb.T4_CONSISTENT_WITH_CLAIMS)
        self.assertAlmostEqual(o.computed_si,10_000_000)
        self.assertAlmostEqual(o.upper_si,50_000_000)

    def test_stress_exceeds_allowance(self):
        r=req();s=stress(r);s.applied_force.CopyFrom(q(10_000,pb.T4_NEWTON))
        self.assertEqual(analyze(r).findings[0].status,pb.T4_CONTRADICTS_CLAIMS)

    def test_safety_factor_bypass_rejected(self):
        for value in (0,.5,math.inf,math.nan,1000001):
            with self.subTest(value=value):
                r=req();s=stress(r);s.safety_factor=value
                self.assert_reject(r,"INVALID_SAFETY_FACTOR")

    def test_stress_zero_area_rejected(self):
        r=req();s=stress(r);s.cross_section_area.CopyFrom(q(0,pb.T4_SQUARE_METER))
        self.assert_reject(r,"NONPOSITIVE_AREA")

    def test_stress_negative_force_rejected(self):
        r=req();s=stress(r);s.applied_force.CopyFrom(q(-1,pb.T4_NEWTON))
        self.assert_reject(r,"NEGATIVE_APPLIED_FORCE")

    def test_stress_missing_force_unknown(self):
        r=req();s=stress(r);s.ClearField("applied_force")
        self.assertEqual(analyze(r).findings[0].status,pb.T4_UNDETERMINED)

    def test_deflection_conversion(self):
        r=req();deflection(r)
        o=analyze(r).findings[0]
        self.assertEqual(o.status,pb.T4_CONSISTENT_WITH_CLAIMS)
        self.assertAlmostEqual(o.computed_si,.001)

    def test_deflection_limit_exceeded(self):
        r=req();d=deflection(r);d.maximum_deflection.CopyFrom(q(.5,pb.T4_MILLIMETER))
        self.assertEqual(analyze(r).findings[0].status,pb.T4_CONTRADICTS_CLAIMS)

    def test_zero_stiffness_rejected(self):
        r=req();d=deflection(r);d.linear_stiffness.CopyFrom(q(0,pb.T4_NEWTON_PER_METER))
        self.assert_reject(r,"NONPOSITIVE_STIFFNESS")

    def test_unknown_and_dimension_wrong(self):
        r=req();f=fit(r);f.bore_diameter.CopyFrom(q(10,pb.T4_NEWTON))
        self.assert_reject(r,"DIMENSION_MISMATCH")
        f.bore_diameter.CopyFrom(q(math.nan,pb.T4_MILLIMETER))
        self.assert_reject(r,"NONFINITE_QUANTITY")
        f.bore_diameter.CopyFrom(q(10,pb.T4_UNIT_UNSPECIFIED))
        self.assert_reject(r,"DIMENSION_MISMATCH")

    def test_hypothetical_produces_unknown(self):
        r=req();f=fit(r);f.bore_diameter.evidence=pb.T4_HYPOTHETICAL
        self.assertEqual(analyze(r).findings[0].status,pb.T4_UNDETERMINED)
        r=req();fit(r);r.parts[0].evidence=pb.T4_INFERRED
        self.assertEqual(analyze(r).findings[0].status,pb.T4_UNDETERMINED)

    def test_hypothetical_violation_only_conditional(self):
        r=req();f=fit(r);f.bore_diameter.evidence=pb.T4_HYPOTHETICAL
        f.shaft_diameter.CopyFrom(q(50,pb.T4_MILLIMETER))
        finding=analyze(r).findings[0]
        self.assertEqual(finding.status,pb.T4_CONTRADICTS_CLAIMS)
        self.assertIn("PROVISIONAL_CLAIMS_NOT_REAL_WORLD_MEASUREMENTS",finding.reasons)

    def test_no_inferred_authority(self):
        r=req();fit(r);r.grants_authority=True
        self.assert_reject(r,"INVALID_RESEARCH_CONTRACT")
        r=req();fit(r);r.research_only=False
        self.assert_reject(r,"INVALID_RESEARCH_CONTRACT")

    def test_scope_and_duplicates(self):
        r=req();fit(r);r.fits.add().CopyFrom(r.fits[0])
        self.assert_reject(r,"INVALID_OR_DUPLICATE_CHECK")
        r=req();fit(r);r.parts.add().CopyFrom(r.parts[0])
        self.assert_reject(r,"DUPLICATE_PART")
        r=req();fit(r);r.graph_id="../../escape"
        self.assert_reject(r,"INVALID_SCOPE")

    def test_self_connection_and_foreign_part(self):
        r=req();f=fit(r);f.bore_part_id="shaft"
        self.assert_reject(r,"SELF_CONNECTION")
        r=req();f=fit(r);f.bore_part_id="other"
        self.assert_reject(r,"UNKNOWN_PART")

    def test_deterministic_order_independent_of_check_order(self):
        r=req();fit(r);joint(r);stress(r);deflection(r)
        a=analyze(r)
        self.assertEqual([f.id for f in a.findings],["fit1","joint1","stress1","deflect1"])
        self.assertEqual(a.SerializeToString(deterministic=True),analyze(r).SerializeToString(deterministic=True))

    def test_repeated_check_count_bounded(self):
        r=req()
        for n in range(129):
            r.fits.add(id=f"f{n}")
        self.assert_reject(r,"RESOURCE_LIMIT")

    def test_unknown_nested_wire_field_rejected(self):
        r=req();fit(r)
        # Unknown field 99 in nested T4Quantity.
        raw = r.fits[0].bore_diameter.SerializeToString() + _VarintBytes((99<<3)|0) + b"\x01"
        r.fits[0].bore_diameter.ParseFromString(raw)
        self.assert_reject(r,"UNKNOWN_PROTO_FIELDS")

    def test_empty_contract_is_not_certification(self):
        o=analyze(req())
        self.assertEqual(len(o.findings),0)
        self.assertFalse(o.physical_validity_verified)
        self.assertTrue(o.research_only)


if __name__ == "__main__":
    unittest.main()
