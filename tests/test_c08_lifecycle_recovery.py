"""Restored HDC derived-index lifecycle acceptance; no canonical memory rights."""
import unittest
from cognitum.research.hdc_index_lifecycle import EphemeralDerivedIndex
from cognitum.proto.research_optional_pb2 import HdcCandidates

ROWS=(("a", "owns", "ship"), ("b", "owns", "station"))


class HdcIndexLifecycleTests(unittest.TestCase):
    def test_ranked_candidates_only_and_generation(self):
        index=EphemeralDerivedIndex()
        self.assertEqual(index.install("snap1", ROWS), 1)
        observed=[]
        self.assertEqual(index.deliver("snap1", "owns", "ship", 2, observed.append), 1)
        result=HdcCandidates.FromString(observed[0])
        self.assertEqual(result.candidate_ids[0], "a")
        self.assertFalse(result.grants_authority)
        self.assertEqual(result.source_snapshot_id, "snap1")

    def test_revision_change_requires_explicit_invalidation(self):
        index=EphemeralDerivedIndex()
        index.install("snap1", ROWS)
        with self.assertRaisesRegex(ValueError, "MUST_INVALIDATE"):
            index.install("snap2", ROWS)
        with self.assertRaisesRegex(ValueError, "STALE"):
            index.deliver("snap2", "owns", "ship", 2, lambda _: None)
        index.invalidate(reason="EDIT")
        with self.assertRaisesRegex(ValueError, "STALE"):
            index.deliver("snap1", "owns", "ship", 2, lambda _: None)
        index.install("snap2", ROWS)
        emitted=[]
        index.deliver("snap2", "owns", "ship", 2, emitted.append)
        self.assertEqual(HdcCandidates.FromString(emitted[0]).source_snapshot_id, "snap2")

    def test_scope_revocation_and_deletion_clear_candidates(self):
        for reason in ("SCOPE_REVOKED", "DELETE", "RETRACT", "SOURCE_REPLACED"):
            index=EphemeralDerivedIndex()
            index.install("snap1", ROWS)
            index.invalidate(reason=reason)
            observed=[]
            with self.assertRaisesRegex(ValueError, "STALE"):
                index.deliver("snap1", "owns", "ship", 2, observed.append)
            self.assertEqual(observed, [])

    def test_duplicate_and_oversized_records_rejected(self):
        index=EphemeralDerivedIndex()
        with self.assertRaisesRegex(ValueError, "INVALID_INDEX_RECORDS"):
            index.install("snap1", [ROWS[0], ROWS[0]])
        with self.assertRaisesRegex(ValueError, "INVALID_INDEX_RECORDS"):
            index.install("snap1", [("source", "owns", "ship")] * 33)

    def test_delivery_is_serialized_against_invalidation(self):
        from threading import Event, Thread
        index=EphemeralDerivedIndex()
        index.install("snap1", ROWS)
        entered, release, finished=Event(), Event(), Event()
        def sink(_):
            entered.set()
            assert release.wait(3)
        writer=Thread(target=lambda: index.deliver(
            "snap1", "owns", "ship", 2, sink
        ))
        writer.start()
        self.assertTrue(entered.wait(3))
        invalidator=Thread(target=lambda: (index.invalidate(reason="EDIT"), finished.set()))
        invalidator.start()
        self.assertFalse(finished.wait(.05))
        release.set()
        writer.join(3)
        invalidator.join(3)
        self.assertTrue(finished.is_set())
        with self.assertRaisesRegex(ValueError, "STALE"):
            index.deliver("snap1", "owns", "ship", 2, lambda _: None)


if __name__=="__main__":
    unittest.main()
