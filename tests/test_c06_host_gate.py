"""C06/P2 host-leased, native Proto reference tests (synthetic, no Lu data)."""
import hashlib
import threading
import unittest
from dataclasses import replace

from cognitum.memory_evidence import TrustedReadContext, encode_frame
from cognitum.memory_host_gate import dispatch_host_fenced, verify_citation_lookup
from cognitum.proto import memory_pb2 as pb


class SyntheticHost:
    """Tests only: simulates host-owned serialized grant state and delivery."""
    def __init__(self, *, text="Decision: Protobuf is native"):
        self.lock = threading.RLock()
        self.owner = threading.get_ident()
        self.live = True
        self.deleted = False
        self.cancelled = False
        self.generation = 7
        self.index_epoch = 3
        self.snapshot_id = "snap-local"
        self.text = text
        self.publisher = []
        self.before_recheck = None
        self.in_lease = False
        self.read_locked_at_publish = False
        self.fail_publish = False

    def acquire(self):
        return HostLease(self)

    def build(self):
        self.context = TrustedReadContext(scope_id="profile-local", snapshot_id=self.snapshot_id,
                                          authorization_epoch=self.generation, index_epoch=self.index_epoch,
                                          authorized_sessions=frozenset({"session-local"}))
        snap = pb.CanonicalSnapshot(schema_version=1, snapshot_id=self.snapshot_id,
                                    scope_id="profile-local", authorization_epoch=self.generation,
                                    index_epoch=self.index_epoch, grant_active=self.live, consistent=True)
        source = pb.SourceRef(session_id="session-local", chapter_id="chapter-local",
                              entry_id="entry-local", revision_id="rev-current")
        snap.records.add(source=source, current_revision_id="rev-current",
                         authorized=self.live, deleted=self.deleted,
                         canonical_text="" if self.deleted or not self.live else self.text)
        self.snapshot_frame = encode_frame(snap)
        query = pb.MemoryQuery(schema_version=1, request_id="req-local", literal_query="Protobuf",
                               max_results=1)
        batch = pb.CandidateBatch(schema_version=1)
        batch.candidates.add(source=source, content_sha256=hashlib.sha256(self.text.encode()).hexdigest(),
                             snapshot_id=self.snapshot_id, scope_id="profile-local",
                             start_utf8_byte=0, length_utf8_byte=len(self.text.encode()))
        return encode_frame(query), encode_frame(batch)


class HostLease:
    def __init__(self, host):
        self.host = host

    def __enter__(self):
        self.host.lock.acquire()
        self.host.in_lease = True
        self.host.build()
        return self

    def __exit__(self, *exc):
        self.host.in_lease = False
        self.host.lock.release()

    @property
    def context(self):
        return self.host.context

    @property
    def snapshot_frame(self):
        return self.host.snapshot_frame

    def recheck(self):
        if self.host.before_recheck:
            self.host.before_recheck(self.host)
        if self.host.cancelled:
            return pb.CANCELLED
        if not self.host.live or self.host.generation != self.context.authorization_epoch:
            return pb.DENIED
        if self.host.deleted:
            return pb.DELETED
        if self.host.index_epoch != self.context.index_epoch or self.host.snapshot_id != self.context.snapshot_id:
            return pb.STALE
        return pb.VERIFIED

    def publish(self, reply_frame):
        self.host.read_locked_at_publish = self.host.in_lease
        if self.host.fail_publish:
            raise RuntimeError("secret source error should never be disclosed")
        self.host.publisher.append(reply_frame)


def as_lookup(host, evidence, *, request_id="lookup-local"):
    return pb.CitationLookup(schema_version=1, request_id=request_id,
                             citation_handle=evidence.citation_handle,
                             source=evidence.source, snapshot_id=evidence.snapshot_id,
                             content_sha256=evidence.content_sha256,
                             start_utf8_byte=evidence.start_utf8_byte,
                             length_utf8_byte=len(evidence.excerpt.encode()))


class HostBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.host = SyntheticHost()
        self.query_frame, self.batch_frame = self.host.build()

    def search(self, *, frame=None, batch=None):
        return dispatch_host_fenced("search", frame if frame is not None else self.query_frame,
                                    gateway=self.host,
                                    candidate_frame=batch if batch is not None else self.batch_frame)

    def latest(self, cls=pb.RetrievalReply):
        return cls.FromString(self.host.publisher[-1])

    def test_search_publishes_validated_host_canonical_bytes_under_host_lease(self):
        receipt = self.search()
        self.assertEqual((receipt.status, receipt.published), (pb.VERIFIED, True))
        self.assertTrue(self.host.read_locked_at_publish)
        self.assertFalse(self.host.in_lease)
        answer = self.latest()
        self.assertEqual(len(answer.evidence), 1)
        self.assertEqual(answer.evidence[0].excerpt, self.host.text)
        self.assertNotIn("excerpt", str(receipt))

    def test_revocation_between_verification_and_publish_drops_all_content(self):
        self.host.before_recheck = lambda host: setattr(host, "live", False)
        receipt = self.search()
        self.assertEqual(receipt.status, pb.DENIED)
        self.assertEqual(self.latest().status, pb.DENIED)
        self.assertEqual(len(self.latest().evidence), 0)
        self.assertNotIn(self.host.text.encode(), self.host.publisher[-1])

    def test_deletion_in_fence_releases_no_content(self):
        self.host.before_recheck = lambda host: setattr(host, "deleted", True)
        self.assertEqual(self.search().status, pb.DELETED)
        self.assertFalse(self.latest().evidence)

    def test_cancelled_host_lease_never_publishes_evidence(self):
        self.host.before_recheck = lambda host: setattr(host, "cancelled", True)
        self.assertEqual(self.search().status, pb.CANCELLED)
        self.assertFalse(self.latest().evidence)
        self.assertTrue(self.host.read_locked_at_publish)

    def test_cancelled_literal_lease_never_publishes_evidence(self):
        self.host.before_recheck = lambda host: setattr(host, "cancelled", True)
        receipt = dispatch_host_fenced("literal", self.query_frame, gateway=self.host)
        self.assertEqual(receipt.status, pb.CANCELLED)
        self.assertFalse(self.latest().evidence)

    def test_revision_index_refresh_is_stale(self):
        self.host.before_recheck = lambda host: setattr(host, "index_epoch", host.index_epoch + 1)
        self.assertEqual(self.search().status, pb.STALE)
        self.assertFalse(self.latest().evidence)

    def test_grant_generation_refresh_is_denied(self):
        self.host.before_recheck = lambda host: setattr(host, "generation", host.generation + 1)
        self.assertEqual(self.search().status, pb.DENIED)
        self.assertFalse(self.latest().evidence)

    def test_host_provided_context_cannot_be_replaced_by_guessed_ids(self):
        candidate = pb.CandidateBatch.FromString(self.batch_frame)
        candidate.candidates[0].scope_id = "guessed_profile"
        result = self.search(batch=encode_frame(candidate))
        self.assertEqual(result.status, pb.DENIED)
        self.assertFalse(self.latest().evidence)

    def test_invalid_candidate_does_not_prevent_final_recheck(self):
        self.host.before_recheck = lambda host: setattr(host, "live", False)
        self.assertEqual(self.search(batch=b"not proto").status, pb.DENIED)
        self.assertEqual(self.latest().status, pb.DENIED)

    def test_empty_or_bogus_gateway_does_not_publish(self):
        class BrokenGateway:
            def acquire(self):
                raise RuntimeError("source with secret text")
        receipt = dispatch_host_fenced("search", self.query_frame,
                                       candidate_frame=self.batch_frame, gateway=BrokenGateway())
        self.assertEqual(receipt, type(receipt)(pb.UNAVAILABLE, False))
        self.assertFalse(self.host.publisher)

    def test_publish_exception_never_escapes_or_logs_source(self):
        self.host.fail_publish = True
        receipt = self.search()
        self.assertEqual(receipt.status, pb.UNAVAILABLE)
        self.assertFalse(receipt.published)
        self.assertEqual(len(self.host.publisher), 0)
        self.assertFalse(self.host.in_lease)

    def test_synthetically_inactive_context_never_returns_evidence(self):
        self.host.before_recheck = None
        original = self.host.build
        def blocked_build():
            result = original()
            self.host.context = replace(self.host.context, active=False)
            return result
        self.host.build = blocked_build
        self.assertEqual(self.search().status, pb.DENIED)
        self.assertFalse(self.latest().evidence)

    def test_citation_lookup_requires_current_source_and_exact_handle(self):
        self.assertEqual(self.search().status, pb.VERIFIED)
        evidence = self.latest().evidence[0]
        self.host.publisher.clear()
        lookup = as_lookup(self.host, evidence)
        receipt = dispatch_host_fenced("citation", encode_frame(lookup), gateway=self.host)
        self.assertEqual(receipt.status, pb.VERIFIED)
        out = self.latest(pb.CitationResolution)
        self.assertEqual(out.evidence.excerpt, self.host.text)
        self.assertTrue(self.host.read_locked_at_publish)
        self.host.publisher.clear()
        lookup.citation_handle = "ref_" + "a" * 64
        self.assertEqual(dispatch_host_fenced("citation", encode_frame(lookup), gateway=self.host).status,
                         pb.STALE)
        self.assertFalse(self.latest(pb.CitationResolution).HasField("evidence"))

    def test_citation_never_bypasses_revocation(self):
        self.search()
        lookup = as_lookup(self.host, self.latest().evidence[0])
        self.host.live = False
        self.host.publisher.clear()
        self.assertEqual(dispatch_host_fenced("citation", encode_frame(lookup), gateway=self.host).status,
                         pb.DENIED)
        self.assertFalse(self.latest(pb.CitationResolution).HasField("evidence"))

    def test_cancelled_citation_lease_never_publishes_evidence(self):
        self.search()
        lookup = as_lookup(self.host, self.latest().evidence[0])
        self.host.publisher.clear()
        self.host.before_recheck = lambda host: setattr(host, "cancelled", True)
        receipt = dispatch_host_fenced("citation", encode_frame(lookup), gateway=self.host)
        self.assertEqual(receipt.status, pb.CANCELLED)
        self.assertFalse(self.latest(pb.CitationResolution).HasField("evidence"))

    def test_citation_cannot_recover_after_canonical_edit(self):
        self.search()
        lookup = as_lookup(self.host, self.latest().evidence[0])
        self.host.text = "updated source, prior citation superseded"
        self.host.publisher.clear()
        self.assertEqual(dispatch_host_fenced("citation", encode_frame(lookup), gateway=self.host).status,
                         pb.STALE)
        self.assertFalse(self.latest(pb.CitationResolution).HasField("evidence"))

    def test_citation_deleted_source_fails_closed(self):
        self.search()
        lookup = as_lookup(self.host, self.latest().evidence[0])
        self.host.deleted = True
        self.host.publisher.clear()
        self.assertEqual(dispatch_host_fenced("citation", encode_frame(lookup), gateway=self.host).status,
                         pb.DELETED)
        self.assertFalse(self.latest(pb.CitationResolution).HasField("evidence"))

    def test_citation_scope_guess_fails_and_never_echoes_content(self):
        self.search()
        lookup = as_lookup(self.host, self.latest().evidence[0])
        lookup.source.session_id = "wrong-session"
        self.host.publisher.clear()
        self.assertEqual(dispatch_host_fenced("citation", encode_frame(lookup), gateway=self.host).status,
                         pb.DENIED)
        self.assertNotIn(self.host.text.encode(), self.host.publisher[-1])

    def test_citation_rejects_unknown_fields_and_incorrect_bytes(self):
        self.search()
        lookup = as_lookup(self.host, self.latest().evidence[0])
        wire = encode_frame(lookup) + b"\xa0\x06\x01"
        self.assertEqual(dispatch_host_fenced("citation", wire, gateway=self.host).status,
                         pb.INVALID)
        self.assertFalse(self.latest(pb.CitationResolution).HasField("evidence"))

    def test_citation_lookup_truncated_and_oversized(self):
        self.assertEqual(dispatch_host_fenced("citation", b"", gateway=self.host).status,
                         pb.INVALID)
        self.assertEqual(dispatch_host_fenced("citation", b"a"*4097, gateway=self.host).status,
                         pb.LIMIT)

    def test_host_recheck_bool_is_not_a_verified_status(self):
        self.host.before_recheck = None
        original = self.host.acquire
        class AmbiguousLease:
            def __init__(self, inner):
                self.inner = inner
            def __enter__(self):
                self.inner.__enter__()
                return self
            def __exit__(self, *args):
                return self.inner.__exit__(*args)
            @property
            def context(self):
                return self.inner.context
            @property
            def snapshot_frame(self):
                return self.inner.snapshot_frame
            def recheck(self):
                return True  # bool compares equal to enum VERIFIED == 1
            def publish(self, data):
                return self.inner.publish(data)
        self.host.acquire = lambda: AmbiguousLease(original())
        self.assertEqual(self.search().status, pb.UNAVAILABLE)
        self.assertFalse(self.latest().evidence)

    def test_untrusted_fuzz_input_fails_closed_without_source_leaks(self):
        from random import Random
        rng = Random(606)
        for _ in range(80):
            frame = rng.randbytes(rng.randint(0, 160))
            receipt = self.search(frame=frame)
            self.assertIn(receipt.status, (pb.INVALID, pb.UNSUPPORTED,
                                          pb.LIMIT, pb.UNAVAILABLE))
            self.assertNotIn(self.host.text.encode(), self.host.publisher[-1])
        for _ in range(80):
            frame = rng.randbytes(rng.randint(0, 160))
            receipt = dispatch_host_fenced("citation", frame, gateway=self.host)
            self.assertIn(receipt.status, (pb.INVALID, pb.UNSUPPORTED,
                                          pb.LIMIT, pb.UNAVAILABLE))
            self.assertNotIn(self.host.text.encode(), self.host.publisher[-1])

    def test_literal_query_to_canonical_verified_evidence(self):
        receipt = dispatch_host_fenced("literal", self.query_frame, gateway=self.host)
        self.assertEqual(receipt.status, pb.VERIFIED)
        self.assertEqual(self.latest().evidence[0].excerpt, self.host.text)
        self.assertTrue(self.host.read_locked_at_publish)

    def test_literal_miss_is_empty_verified_batch(self):
        query = pb.MemoryQuery.FromString(self.query_frame)
        query.literal_query = "unmentioned-value"
        reply = dispatch_host_fenced("literal", encode_frame(query), gateway=self.host)
        self.assertEqual(reply.status, pb.VERIFIED)
        self.assertFalse(self.latest().evidence)

    def test_literal_unicode_query_has_utf8_aligned_offsets(self):
        query = pb.MemoryQuery.FromString(self.query_frame)
        query.literal_query = "💡"
        self.host.text = "prefix α💡 decision"
        reply = dispatch_host_fenced("literal", encode_frame(query), gateway=self.host)
        self.assertEqual(reply.status, pb.VERIFIED)
        self.assertEqual(self.latest().evidence[0].excerpt, "prefix α💡 decision")

    def test_literal_query_filters_exact_sources(self):
        query = pb.MemoryQuery.FromString(self.query_frame)
        query.exact_sources.add(session_id="session-local", chapter_id="chapter-local",
                                entry_id="unmatched", revision_id="rev-current")
        receipt = dispatch_host_fenced("literal", encode_frame(query), gateway=self.host)
        self.assertEqual(receipt.status, pb.VERIFIED)
        self.assertFalse(self.latest().evidence)

    def test_literal_disallows_external_candidate_frame(self):
        receipt = dispatch_host_fenced("literal", self.query_frame, gateway=self.host,
                                       candidate_frame=self.batch_frame)
        self.assertEqual(receipt.status, pb.INVALID)
        self.assertFalse(self.latest().evidence)

    def test_literal_revocation_between_selection_and_publish(self):
        self.host.before_recheck = lambda host: setattr(host, "live", False)
        receipt = dispatch_host_fenced("literal", self.query_frame, gateway=self.host)
        self.assertEqual(receipt.status, pb.DENIED)
        self.assertFalse(self.latest().evidence)

    def test_literal_bounded_result_count_current_first(self):
        original = self.host.build
        def enriched_build():
            frames = original()
            snap = pb.CanonicalSnapshot.FromString(self.host.snapshot_frame)
            for number in range(10):
                ref = pb.SourceRef(session_id="session-local", chapter_id="chapter-local",
                                   entry_id=f"other{number}", revision_id="rev-current")
                snap.records.add(source=ref, current_revision_id="rev-current",
                                 authorized=True, canonical_text="Protobuf plus evidence")
            self.host.snapshot_frame = encode_frame(snap)
            return frames
        self.host.build = enriched_build
        query = pb.MemoryQuery.FromString(self.query_frame)
        query.max_results = 3
        receipt = dispatch_host_fenced("literal", encode_frame(query), gateway=self.host)
        self.assertEqual(receipt.status, pb.VERIFIED)
        ids = [entry.source.entry_id for entry in self.latest().evidence]
        self.assertEqual(ids, ["entry-local", "other0", "other1"])

    def test_literal_rejects_malformed_or_unavailable_snapshot(self):
        original = self.host.build
        def broken_build():
            out = original()
            self.host.snapshot_frame = b"bad frame"
            return out
        self.host.build = broken_build
        receipt = dispatch_host_fenced("literal", self.query_frame, gateway=self.host)
        self.assertEqual(receipt.status, pb.INVALID)
        self.assertFalse(self.latest().evidence)

    def test_invalid_operation_must_fail_without_opening_host_grant(self):
        with self.assertRaises(ValueError):
            dispatch_host_fenced("write", self.query_frame, gateway=self.host)
        self.assertFalse(self.host.publisher)

    def test_revoke_waits_for_publish_lock_host_implementation(self):
        # The fake host's lock guards lease and publish. A real Lu host must
        # implement this in its own authenticated source executor.
        entered = threading.Event()
        attempt = threading.Event()
        revoked = threading.Event()
        def publisher_thread():
            with self.host.acquire() as lease:
                entered.set()
                attempt.wait(2)
                self.assertEqual(lease.recheck(), pb.VERIFIED)
                lease.publish(b"opaque-test-reply")
        def revoker_thread():
            entered.wait(2)
            attempt.set()
            with self.host.lock:
                self.host.live = False
                revoked.set()
        t1 = threading.Thread(target=publisher_thread)
        t2 = threading.Thread(target=revoker_thread)
        t1.start(); t2.start(); t1.join(5); t2.join(5)
        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())
        self.assertTrue(revoked.is_set())
        self.assertEqual(self.host.publisher, [b"opaque-test-reply"])
        self.assertFalse(self.host.live)


if __name__ == "__main__":
    unittest.main()
