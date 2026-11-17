"""C08 conventional retrieval control: exact map, SQLite FTS5, HDC verifier.

Measures separate query latency on the SAME synthetic canonical records.
FTS5 indexing is timed independently. This does not claim production speed,
hardware advantage, model task quality or energy improvements.
"""
from __future__ import annotations

from statistics import median
from time import perf_counter
import json
import sqlite3

from cognitum.proto import research_optional_pb2 as pb
from cognitum.research.hdc_optional import query
from cognitum.research.hdc_canonical import CanonicalRelation, verify_hdc_candidates


def run():
    records = []
    for i in range(32):
        records.append(CanonicalRelation(
            f"source{i}", 1, "alice",
            "owns" if i % 3 == 0 else "visits",
            "ship" if i % 4 == 0 else "station",
            f"ansf:source:{i}",
        ))
    # Source 0 is no longer available even if its old vector ranks first.
    records.append(CanonicalRelation(
        "source0", 2, "bob", "owns", "ship", "ansf:source:0:v2",
    ))
    latest = {}
    for record in records:
        if record.source_id not in latest or record.revision > latest[record.source_id].revision:
            latest[record.source_id] = record

    t0 = perf_counter()
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE relations USING fts5(role, entity)")
        ordered = sorted(latest.values(), key=lambda r: r.source_id)
        conn.executemany(
            "INSERT INTO relations(rowid, role, entity) VALUES (?, ?, ?)",
            ((i + 1, row.role, row.entity) for i, row in enumerate(ordered)),
        )
        index_ms = (perf_counter() - t0) * 1000
        samples = {name: [] for name in ("exact_ms", "fts5_ms", "hdc_ms")}
        recalls = {name: [] for name in ("exact", "fts5", "hdc")}
        for trial in range(60):
            role = ("owns" if trial % 2 == 0 else "visits")
            entity = ("ship" if trial % 3 == 0 else "station")
            expected = {source for source, item in latest.items()
                        if item.scope == "alice" and not item.tombstone
                        and item.role == role and item.entity == entity}

            t1 = perf_counter()
            exact = {source for source, item in latest.items()
                     if item.scope == "alice" and not item.tombstone
                     and item.role == role and item.entity == entity}
            t2 = perf_counter()
            rows = conn.execute(
                "SELECT rowid FROM relations WHERE relations MATCH ?",
                (f'"{role}" AND "{entity}"',),
            ).fetchall()
            fts = {
                ordered[rowid - 1].source_id for (rowid,) in rows
                if ordered[rowid - 1].scope == "alice"
                and not ordered[rowid - 1].tombstone
            }
            t3 = perf_counter()

            req = pb.HdcQuery(
                schema_version=1, source_snapshot_id="snapshot",
                index_snapshot_id="snapshot", role=role, entity=entity, top_k=8,
            )
            for r in records[:32]:
                req.records.add(candidate_id=r.source_id, role=r.role, entity=r.entity)
            request_wire = req.SerializeToString(deterministic=True)
            verified = verify_hdc_candidates(
                request_wire, query(request_wire),
                canonical_records=records, authorized_scope="alice",
                canonical_snapshot_id="snapshot",
                current_snapshot_id="snapshot", required_revision=2,
            )
            hdc = {item.source_id for item in verified.verified}
            t4 = perf_counter()
            if not (exact <= expected and fts <= expected and hdc <= expected):
                raise AssertionError("unauthorized or false-positive source")
            for name, ids in (("exact", exact), ("fts5", fts), ("hdc", hdc)):
                recalls[name].append(len(ids & expected) / len(expected) if expected else 1)
            samples["exact_ms"].append((t2 - t1) * 1000)
            samples["fts5_ms"].append((t3 - t2) * 1000)
            samples["hdc_ms"].append((t4 - t3) * 1000)

        return {
            "label": "synthetic-C08-conventional-32-canonical-records",
            "not_production_evidence": True,
            "trials": 60,
            "fts5_build_ms": round(index_ms, 4),
            "median_query_ms": {
                name[:-3]: round(median(values), 4)
                for name, values in samples.items()
            },
            "mean_recall": {
                name: round(sum(values) / len(values), 4)
                for name, values in recalls.items()
            },
            "note": "FTS5 and exact use canonical current records; HDC also pays Protobuf and canonical recheck costs",
        }
    finally:
        conn.close()


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
