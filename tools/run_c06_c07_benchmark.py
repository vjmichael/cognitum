"""Deterministic C06 conventional retrieval baseline; no model superiority claim."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from statistics import median
from time import perf_counter

from cognitum.memory_retrieval import MemoryEvidence, MemoryQuery, retrieve

T = datetime(2026, 11, 4, tzinfo=timezone.utc)


def run():
    records = []
    # Deterministic scenario: 1200 canonical records, two per indexed subject,
    # with a corrected revision, a tombstoned source and a foreign scope.
    for i in range(1200):
        records.append(MemoryEvidence(
            source_id=f"s-{i}", revision=1,
            access_scope="allowed" if i % 7 else "foreign",
            subject=f"colony-{i}",
            text=f"Survey on colony {i} found geology sector {i % 11} and supplies.",
            citation_handle=f"cite:{i}", valid_from=T,
        ))
    records.extend([
        MemoryEvidence("s-43", 2, "allowed", "colony-43",
                       "No longer supplies; atmospheric vents updated.",
                       "cite:43:new", T),
        MemoryEvidence("s-44", 2, "allowed", "colony-44",
                       "obsolete", "cite:44:delete", T, tombstone=True),
    ])

    cases = [
        (MemoryQuery("allowed", "geology sector 5", as_of=T), None),
        (MemoryQuery("allowed", "atmospheric vents", as_of=T), "s-43"),
        (MemoryQuery("allowed", "qzznonexistenttoken", as_of=T), None),
        (MemoryQuery("foreign", "atmospheric vents", as_of=T), None),
    ]
    modes = {}
    for mode in ("exact", "fts5"):
        elapsed = []
        correct = 0
        for query, expected in cases:
            start = perf_counter()
            response = retrieve(
                records, query, snapshot_id="benchmark-snapshot",
                origin_revision=2, ranking=mode,
            )
            elapsed.append((perf_counter() - start) * 1000)
            ids = {record.source_id for record in response.evidence}
            if expected is None:
                correct += int(not ids) if "qzz" in query.text or query.scope == "foreign" else int(bool(ids))
            else:
                correct += int(expected in ids)
            if "s-44" in ids:
                raise AssertionError("tombstone surfaced")
        modes[mode] = {
            "scenarios": len(cases),
            "scenario_checks_passed": correct,
            "median_ms": round(median(elapsed), 3),
            "total_ms": round(sum(elapsed), 3),
        }
    return {
        "benchmark": "synthetic-C06-1200-record-lexical-reference",
        "claims": "synthetic retrieval baseline only; no Lu/model end-task measurement",
        "records": len(records),
        "modes": modes,
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
