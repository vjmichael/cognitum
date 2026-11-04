"""Reference acceptance for C06/C07; no host storage or authorization is claimed."""
from datetime import datetime, timedelta, timezone

import pytest

from cognitum.memory_retrieval import (
    MemoryEvidence, MemoryQuery, RetrievalError, retrieve,
)
from cognitum.state_revision import (
    Action, Origin, StateError, StateEvent, replay,
)

T = datetime(2026, 11, 4, tzinfo=timezone.utc)


def memory(source="s1", revision=1, *, scope="alice", text="colony supplies", tombstone=False):
    return MemoryEvidence(source, revision, scope, "colony", text, f"cite:{source}:{revision}", T, None, tombstone)


def event(eid, action, revision, value="ready", source="user"):
    return StateEvent(eid, "ship", "status", value, Origin.USER_DECISION,
                      "host-approved", revision, T, T, action, source)


def test_c06_scopes_and_snapshot_revision():
    records = [memory(), memory("s2", scope="bob"), memory("s3", text="other subject")]
    got = retrieve(records, MemoryQuery("alice", "colony supplies", as_of=T),
                   snapshot_id="snapshot-1", origin_revision=1)
    assert [x.source_id for x in got.evidence] == ["s1"]
    with pytest.raises(RetrievalError, match="stale"):
        retrieve(records, MemoryQuery("alice", as_of=T), snapshot_id="s",
                 origin_revision=1, expected_origin_revision=2)


def test_c06_tombstone_hides_previous_citation():
    records = [memory(), memory(revision=2, tombstone=True)]
    result = retrieve(iter(records), MemoryQuery("alice", "supplies", as_of=T),
                      snapshot_id="s", origin_revision=2)
    assert result.evidence == ()


def test_c06_new_revision_not_matching_query_suppresses_old_revision():
    result = retrieve([memory(), memory(revision=2, text="no longer relevant")],
                      MemoryQuery("alice", "supplies", as_of=T),
                      snapshot_id="s", origin_revision=2)
    assert result.evidence == ()


def test_c06_rejects_cross_snapshot_records_and_duplicates():
    with pytest.raises(RetrievalError, match="newer"):
        retrieve([memory(revision=3)], MemoryQuery("alice", as_of=T),
                 snapshot_id="s", origin_revision=2)
    with pytest.raises(RetrievalError, match="duplicate"):
        retrieve([memory(), memory()], MemoryQuery("alice", as_of=T),
                 snapshot_id="s", origin_revision=1)


def test_c07_idempotency_and_typed_origin():
    a, b = event("a", Action.ASSERT, 0), event("b", Action.CONFIRM, 1)
    result = replay([a, a, b])
    assert result.event_count == 2
    assert result.claims[0].revision == 2
    assert result.claims[0].origin is Origin.USER_DECISION
    assert result.claims[0].status == "ACTIVE"


def test_c07_challenge_and_retraction_preserve_evidence():
    result = replay([event("a", Action.ASSERT, 0),
                     event("b", Action.CHALLENGE, 1, source="observer"),
                     event("c", Action.RETRACT, 2)])
    claim = result.claims[0]
    assert claim.status == "RETRACTED"
    assert claim.conflict_refs == ("observer",)
    assert claim.source_refs == ("user", "observer")


def test_c07_stale_and_forged_event_id_rejected():
    with pytest.raises(StateError, match="stale"):
        replay([event("a", Action.ASSERT, 0), event("b", Action.CONFIRM, 0)])
    with pytest.raises(StateError, match="reused"):
        replay([event("a", Action.ASSERT, 0), event("a", Action.ASSERT, 1)])


def test_c07_no_unilateral_overwrite():
    with pytest.raises(StateError, match="assert"):
        replay([event("a", Action.ASSERT, 0), event("b", Action.ASSERT, 1, "forged")])


def test_c07_retracted_claim_can_be_reasserted():
    result = replay([event("a", Action.ASSERT, 0),
                     event("b", Action.RETRACT, 1),
                     event("c", Action.ASSERT, 2, "reopened")])
    assert result.claims[0].typed_value == "reopened"
    assert result.claims[0].revision == 3


def test_import_and_model_cannot_overwrite_verified_user_decision():
    original = event("a", Action.ASSERT, 0)
    for origin in (Origin.IMPORTED_CLAIM, Origin.MODEL_HYPOTHESIS):
        malicious = StateEvent(
            "b", "ship", "status", "forged", origin, "opaque",
            1, T, T, Action.SUPERSEDE, "untrusted",
        )
        with pytest.raises(StateError, match="cannot override"):
            replay([original, malicious])
    # Contesting a claim is allowed; silently replacing it is not.
    notice = StateEvent(
        "b", "ship", "status", "different", Origin.IMPORTED_CLAIM,
        "host-opaque", 1, T, T, Action.CHALLENGE, "outside",
    )
    snapshot = replay([original, notice])
    assert snapshot.claims[0].typed_value == "ready"
    assert snapshot.claims[0].conflict_refs == ("outside",)


def test_reject_untyped_and_oversized_events():
    with pytest.raises(StateError, match="typed value"):
        StateEvent("a", "ship", "status", {"injected": True},
                   Origin.MODEL_HYPOTHESIS, "opaque", 0, T, T,
                   Action.ASSERT, "source")
    with pytest.raises(StateError, match="64-bit"):
        StateEvent("a", "ship", "status", 2 ** 72,
                   Origin.MODEL_HYPOTHESIS, "opaque", 0, T, T,
                   Action.ASSERT, "source")
