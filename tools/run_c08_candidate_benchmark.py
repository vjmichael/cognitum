"""C08 deterministic quantitative candidate-vs-exact controls.

These small synthetic tests establish error accounting and cost; they do NOT
claim HDC improves Lu's end-task accuracy or beats FTS5 at scale.
"""
from __future__ import annotations

import json
from statistics import median
from time import perf_counter

from cognitum.proto import research_optional_pb2 as pb
from cognitum.research.hdc_optional import query
from cognitum.research.hdc_canonical import CanonicalRelation, verify_hdc_candidates


def run():
    samples = []
    for seed in range(20):
        request = pb.HdcQuery(
            schema_version=1, source_snapshot_id=f"snapshot{seed}",
            index_snapshot_id=f"snapshot{seed}", role="owns",
            entity="ship", top_k=8,
        )
        canonical = []
        for i in range(32):
            source = f"source{i}"
            role = "owns" if i % 3 == 0 else "visits"
            entity = "ship" if i % 4 == 0 else "station"
            request.records.add(candidate_id=source, role=role, entity=entity)
            canonical.append(CanonicalRelation(
                source, 1, "alice", role, entity, f"ansf:source:{source}",
            ))
        # A previously accurate candidate whose source has been re-scoped
        # or deleted cannot pass the post-retrieval verification.
        canonical.append(CanonicalRelation(
            "source0", 2, "bob" if seed % 2 == 0 else "alice",
            "owns", "ship", "ansf:source:source0:v2",
            tombstone=seed % 2 == 1,
        ))
        raw = request.SerializeToString(deterministic=True)
        t0 = perf_counter()
        candidates = pb.HdcCandidates.FromString(query(raw))
        t1 = perf_counter()
        result = verify_hdc_candidates(
            raw, candidates.SerializeToString(deterministic=True),
            canonical_records=canonical, authorized_scope="alice",
            canonical_snapshot_id=f"snapshot{seed}",
            current_snapshot_id=f"snapshot{seed}", required_revision=2,
        )
        t2 = perf_counter()
        verified = {entry.source_id for entry in result.verified}
        # Ground truth is the current canonical set in the authorized scope.
        latest = {}
        for record in canonical:
            if record.source_id not in latest or record.revision > latest[record.source_id].revision:
                latest[record.source_id] = record
        truth = {
            source for source, record in latest.items()
            if record.scope == "alice" and not record.tombstone
            and record.role == "owns" and record.entity == "ship"
        }
        if not verified.issubset(truth):
            raise AssertionError("C08 verified hit is not canonical truth")
        samples.append({
            "candidate_ms": (t1 - t0) * 1000,
            "verify_ms": (t2 - t1) * 1000,
            "candidate_count": len(candidates.candidate_ids),
            "verified_count": len(verified),
            "precision": len(verified) / max(len(verified), 1),
            "recall": len(verified & truth) / len(truth) if truth else 1.0,
            "false_positive_count": len(verified - truth),
        })
    report = {
        "label": "synthetic-HDC-BSC-32-records-20-cases",
        "not_claimed": "no Lu model, real ANSF API, power or FTS5 benchmark here",
        "samples": len(samples),
        "median_candidate_ms": round(median(s["candidate_ms"] for s in samples), 4),
        "median_verifier_ms": round(median(s["verify_ms"] for s in samples), 4),
        "verified_false_positives": sum(s["false_positive_count"] for s in samples),
        "mean_verified_recall": round(sum(s["recall"] for s in samples) / len(samples), 4),
        "verified_recall_not_guaranteed": True,
    }
    return report


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
