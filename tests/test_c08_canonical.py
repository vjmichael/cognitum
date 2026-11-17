"""C08 host-source validation: no HDC candidate becomes authority."""
import unittest

from cognitum.proto import research_optional_pb2 as pb
from cognitum.research.hdc_optional import query
from cognitum.research.hdc_canonical import CanonicalRelation, verify_hdc_candidates


def request():
    req = pb.HdcQuery(
        schema_version=1, source_snapshot_id="snapshot1",
        index_snapshot_id="snapshot1", role="owns", entity="ship", top_k=3,
    )
    req.records.add(candidate_id="a", role="owns", entity="ship")
    req.records.add(candidate_id="b", role="owns", entity="station")
    req.records.add(candidate_id="c", role="visits", entity="ship")
    return req.SerializeToString(deterministic=True)


def rec(source, revision=1, scope="alice", role="owns", entity="ship",
        tombstone=False):
    return CanonicalRelation(source, revision, scope, role, entity,
                             f"lu:source:{source}:{revision}", tombstone)


def verify(raw, records, result=None, **kwargs):
    return verify_hdc_candidates(
        raw, result if result is not None else query(raw),
        canonical_records=iter(records), authorized_scope="alice",
        canonical_snapshot_id="snapshot1", current_snapshot_id="snapshot1",
        required_revision=2, **kwargs,
    )


class HdcCanonicalAcceptance(unittest.TestCase):
    def test_only_exact_authorized_revisions_are_returned(self):
        raw = request()
        result = verify(raw, [rec("a"), rec("b", entity="station"),
                              rec("c", role="visits")])
        self.assertEqual([v.source_id for v in result.verified], ["a"])
        self.assertEqual(len(result.rejected), 2)
        self.assertEqual(result.verified[0].citation_handle, "lu:source:a:1")

    def test_canonical_tombstone_overrides_old_index(self):
        result = verify(request(), [rec("a"), rec("a", 2, tombstone=True)])
        self.assertFalse(result.verified)
        self.assertIn("a", result.rejected)

    def test_rescoped_source_cannot_leak_previous_revision(self):
        result = verify(request(), [rec("a"), rec("a", 2, scope="bob")])
        self.assertFalse(result.verified)

    def test_updated_relation_cannot_use_old_hdc_binding(self):
        result = verify(request(), [rec("a"), rec("a", 2, entity="moon")])
        self.assertFalse(result.verified)

    def test_unverified_candidate_is_not_sufficient(self):
        result = verify(request(), [])
        self.assertFalse(result.verified)
        self.assertEqual(len(result.rejected), 3)

    def test_stale_host_snapshot_rejected(self):
        raw = request()
        with self.assertRaisesRegex(ValueError, "STALE"):
            verify_hdc_candidates(
                raw, query(raw), canonical_records=[rec("a")],
                authorized_scope="alice", canonical_snapshot_id="snapshot1",
                current_snapshot_id="snapshot2", required_revision=2,
            )

    def test_forged_ranking_and_distance_rejected(self):
        raw = request()
        forged = pb.HdcCandidates.FromString(query(raw))
        forged.hamming_distance[0] += 1
        with self.assertRaisesRegex(ValueError, "FORGED"):
            verify(raw, [rec("a")], forged.SerializeToString(deterministic=True))

    def test_forged_authority_rejected(self):
        raw = request()
        forged = pb.HdcCandidates.FromString(query(raw))
        forged.grants_authority = True
        with self.assertRaisesRegex(ValueError, "UNTRUSTED"):
            verify(raw, [rec("a")], forged.SerializeToString(deterministic=True))

    def test_duplicate_canonical_revision_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CANONICAL"):
            verify(request(), [rec("a"), rec("a")])

    def test_future_revision_rejected(self):
        with self.assertRaisesRegex(ValueError, "FUTURE"):
            verify(request(), [rec("a", revision=3)])

    def test_unknown_proto_field_rejected(self):
        raw = request()
        with self.assertRaisesRegex(ValueError, "NONCANONICAL"):
            verify(raw, [rec("a")], query(raw) + b"\x98\x06\x01")

    def test_probe_replay_deterministic(self):
        raw = request()
        records = [rec("a"), rec("b", entity="station"), rec("c", role="visits")]
        self.assertEqual(verify(raw, records), verify(raw, records))


if __name__ == "__main__":
    unittest.main()
