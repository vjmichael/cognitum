"""C15 T2/T3 P2 cross-evidence safety, contradiction, and property checks."""
import unittest
from copy import deepcopy
from cognitum.proto import spatial_composition_pb2 as s
from cognitum.proto import spatial_volume_pb2 as v
from cognitum.proto import spatial_structural_audit_pb2 as a
from cognitum.spatial_structural_audit import audit, StructuralAuditRejected
from tests.test_c15_t2_composition import fixture as graph_fixture
from tests.test_c15_t3_volume import fixture as grid_fixture, add


def base(what=a.SPATIAL_EXPECT_OCCUPIED, node='wall', bounds=(1,1,1,1,1,1)):
    g=graph_fixture(); vol=grid_fixture()
    req=a.StructuralAuditRequest(schema_version=1, conversation_id='thread',graph_id='building',volume_id='shell',research_only=True)
    c=req.claims.add(claim_id='claim_1',node_id=node,source_ref='proposal_1',expected=what)
    c.box.min_x,c.box.min_y,c.box.min_z,c.box.max_x,c.box.max_y,c.box.max_z=bounds
    return g,vol,req


class StructuralAuditTests(unittest.TestCase):
    def out(self, g, volume, req):
        r=audit(g,volume,req)
        self.assertTrue(r.research_only)
        self.assertFalse(r.grants_authority)
        self.assertIn('MEASURED_IS_CALLER_ASSERTED_NOT_AUTHENTICATED',r.warnings)
        return r.audits[0]

    def test_supported_cell_is_only_consistent_not_verified(self):
        g,grid,req=base();add(grid,(1,1,1),v.VOLUME_MEASURED_OCCUPIED)
        self.assertEqual(self.out(g,grid,req).state,a.SPATIAL_AUDIT_CONSISTENT_WITH_CLAIMED_EVIDENCE)

    def test_contradiction(self):
        g,grid,req=base();add(grid,(1,1,1),v.VOLUME_MEASURED_FREE)
        r=self.out(g,grid,req)
        self.assertEqual(r.state,a.SPATIAL_AUDIT_CONTRADICTED_BY_CLAIMED_EVIDENCE)
        self.assertEqual(r.claimed_contradiction_cells,1)

    def test_predicted_free_does_not_validate_void(self):
        g,grid,req=base(a.SPATIAL_EXPECT_FREE)
        add(grid,(1,1,1),v.VOLUME_PREDICTED_FREE)
        r=self.out(g,grid,req)
        self.assertEqual(r.state,a.SPATIAL_AUDIT_INDETERMINATE)
        self.assertEqual(r.predicted_only_cells,1)

    def test_no_measurements_is_indeterminate(self):
        g,grid,req=base()
        self.assertEqual(self.out(g,grid,req).state,a.SPATIAL_AUDIT_INDETERMINATE)

    def test_measured_free_for_void(self):
        g,grid,req=base(a.SPATIAL_EXPECT_FREE)
        add(grid,(1,1,1),v.VOLUME_MEASURED_FREE)
        self.assertEqual(self.out(g,grid,req).state,a.SPATIAL_AUDIT_CONSISTENT_WITH_CLAIMED_EVIDENCE)

    def test_conflicting_sensors_stay_mixed(self):
        g,grid,req=base()
        add(grid,(1,1,1),v.VOLUME_MEASURED_FREE,'lidar')
        add(grid,(1,1,1),v.VOLUME_MEASURED_OCCUPIED,'radar')
        r=self.out(g,grid,req)
        self.assertEqual(r.state,a.SPATIAL_AUDIT_MIXED)
        self.assertEqual(r.conflicting_cells,1)

    def test_partial_coverage_does_not_pass(self):
        g,grid,req=base(bounds=(1,1,1,2,1,1))
        add(grid,(1,1,1),v.VOLUME_MEASURED_OCCUPIED)
        r=self.out(g,grid,req)
        self.assertEqual(r.state,a.SPATIAL_AUDIT_INDETERMINATE)
        self.assertEqual((r.claimed_support_cells,r.unresolved_cells),(1,1))

    def test_partially_contradicted_region_not_pass(self):
        g,grid,req=base(bounds=(1,1,1,2,1,1))
        add(grid,(1,1,1),v.VOLUME_MEASURED_FREE)
        r=self.out(g,grid,req)
        self.assertEqual(r.state,a.SPATIAL_AUDIT_CONTRADICTED_BY_CLAIMED_EVIDENCE)

    def test_same_region_supports_and_contradicts(self):
        g,grid,req=base(bounds=(1,1,1,2,1,1))
        add(grid,(1,1,1),v.VOLUME_MEASURED_OCCUPIED)
        add(grid,(2,1,1),v.VOLUME_MEASURED_FREE)
        self.assertEqual(self.out(g,grid,req).state,a.SPATIAL_AUDIT_MIXED)

    def test_later_same_source_supersedes(self):
        g,grid,req=base()
        add(grid,(1,1,1),v.VOLUME_MEASURED_OCCUPIED,tick=1)
        add(grid,(1,1,1),v.VOLUME_MEASURED_FREE,tick=2)
        self.assertEqual(self.out(g,grid,req).state,a.SPATIAL_AUDIT_CONTRADICTED_BY_CLAIMED_EVIDENCE)

    def test_hypothetical_part_cannot_self_certify(self):
        g,grid,req=base(node='pipe')
        self.assertEqual(self.out(g,grid,req).state,a.SPATIAL_AUDIT_INDETERMINATE)

    def test_label_does_not_generate_volume(self):
        g,grid,req=base()
        g.nodes[1].kind='bone'
        self.assertEqual(self.out(g,grid,req).state,a.SPATIAL_AUDIT_INDETERMINATE)

    def test_only_voxels_in_claimed_region(self):
        g,grid,req=base()
        add(grid,(3,3,3),v.VOLUME_MEASURED_OCCUPIED)
        self.assertEqual(self.out(g,grid,req).state,a.SPATIAL_AUDIT_INDETERMINATE)

    def test_composition_and_volume_unchanged(self):
        g,grid,req=base();add(grid,(1,1,1),v.VOLUME_MEASURED_OCCUPIED)
        first=(g.SerializeToString(),grid.SerializeToString(),req.SerializeToString())
        self.out(g,grid,req)
        self.assertEqual(first,(g.SerializeToString(),grid.SerializeToString(),req.SerializeToString()))

    def test_two_claims_can_disagree_without_mutating(self):
        g,grid,req=base();add(grid,(1,1,1),v.VOLUME_MEASURED_OCCUPIED)
        other=req.claims.add();other.CopyFrom(req.claims[0]);other.claim_id='claim_2';other.expected=a.SPATIAL_EXPECT_FREE
        states=[x.state for x in audit(g,grid,req).audits]
        self.assertEqual(states,[a.SPATIAL_AUDIT_CONSISTENT_WITH_CLAIMED_EVIDENCE,a.SPATIAL_AUDIT_CONTRADICTED_BY_CLAIMED_EVIDENCE])

    def test_scope_mismatch(self):
        for target,field,value in [('request','conversation_id','other'),('request','graph_id','other'),('request','volume_id','other'),('grid','conversation_id','other'),('graph','conversation_id','other')]:
            with self.subTest(target=target,field=field):
                g,grid,req=base()
                setattr({'request':req,'grid':grid,'graph':g}[target],field,value)
                with self.assertRaisesRegex(StructuralAuditRejected,'SCOPE'):audit(g,grid,req)

    def test_missing_node(self):
        g,grid,req=base(node='intruder')
        with self.assertRaisesRegex(StructuralAuditRejected,'NODE'):audit(g,grid,req)

    def test_no_fake_authority(self):
        g,grid,req=base();req.grants_authority=True
        with self.assertRaises(StructuralAuditRejected):audit(g,grid,req)

    def test_requires_proposal_source(self):
        g,grid,req=base();req.claims[0].source_ref=''
        with self.assertRaisesRegex(StructuralAuditRejected,'PROVENANCE'):audit(g,grid,req)

    def test_duplicate_claim_id(self):
        g,grid,req=base();req.claims.add().CopyFrom(req.claims[0])
        with self.assertRaisesRegex(StructuralAuditRejected,'DUPLICATE'):audit(g,grid,req)

    def test_missing_box_rejected(self):
        g,grid,req=base();req.claims[0].ClearField('box')
        with self.assertRaisesRegex(StructuralAuditRejected,'BOUNDS'):audit(g,grid,req)

    def test_unrecognized_expectation_rejected(self):
        g,grid,req=base();req.claims[0].expected=a.SPATIAL_EXPECTATION_UNSPECIFIED
        with self.assertRaisesRegex(StructuralAuditRejected,'EXPECTATION'):audit(g,grid,req)

    def test_box_out_of_bounds_rejected(self):
        for bb in [(-1,0,0,1,1,1),(0,0,0,10,1,1),(2,2,2,1,1,1)]:
            with self.subTest(bounds=bb):
                g,grid,req=base(bounds=bb)
                with self.assertRaisesRegex(StructuralAuditRejected,'BOUNDS'):audit(g,grid,req)

    def test_box_resource_exhaustion(self):
        g,grid,req=base(bounds=(0,0,0,9,9,9))
        with self.assertRaisesRegex(StructuralAuditRejected,'RESOURCE'):audit(g,grid,req)

    def test_too_many_claims(self):
        g,grid,req=base()
        for i in range(65):
            c=req.claims.add();c.CopyFrom(req.claims[0]);c.claim_id=f'extra_{i}'
        with self.assertRaisesRegex(StructuralAuditRejected,'RESOURCE'):audit(g,grid,req)

    def test_invalid_underlying_volume_fails_closed(self):
        g,grid,req=base();grid.grants_authority=True
        with self.assertRaises(ValueError):audit(g,grid,req)

    def test_invalid_underlying_graph_fails_closed(self):
        g,grid,req=base();g.grants_authority=True
        with self.assertRaises(ValueError):audit(g,grid,req)

    def test_exact_cell_counts_three_state(self):
        g,grid,req=base(bounds=(0,0,0,3,0,0))
        add(grid,(0,0,0),v.VOLUME_MEASURED_OCCUPIED)
        add(grid,(1,0,0),v.VOLUME_MEASURED_FREE)
        add(grid,(2,0,0),v.VOLUME_PREDICTED_OCCUPIED)
        r=self.out(g,grid,req)
        self.assertEqual((r.claimed_support_cells,r.claimed_contradiction_cells,r.unresolved_cells,r.predicted_only_cells,r.total_cells),(1,1,2,1,4))

    def test_reproducibility(self):
        g,grid,req=base();add(grid,(1,1,1),v.VOLUME_MEASURED_FREE)
        self.assertEqual(audit(g,grid,req).SerializeToString(),audit(g,grid,req).SerializeToString())

if __name__=='__main__':unittest.main()
