"""Fail-closed C01-C19 integration source inventory.

This gate tests one *combined tree*. It deliberately does not count open PRs,
synthetic tests, source-file presence, or earlier branch CI as release evidence.
The host integration/OS authorization gate is separate and remains unverified
until an independent Lu ↔ Cognitum installed-app acceptance is recorded.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = {
    "C01": "cognitum/contracts.py",
    "C02": "cognitum/worker_wire.py",
    "C03": "cognitum/evaluation.py",
    "C04": "cognitum/lu_collector_receipt.py",
    "C05": "cognitum/scientific_math.py",
    "C06": "cognitum/memory_retrieval.py",
    "C07": "cognitum/state_revision.py",
    "C08": "cognitum/research/hdc_optional.py",
    "C09": "cognitum/research/kan_optional.py",
    "C10": "cognitum/formal_proofs.py",
    "C11": "cognitum/optimization_wire.py",
    "C12": "cognitum/planning_graph.py",
    "C13": "cognitum/probability_wire.py",
    "C14": "cognitum/causal_specialists.py",
    "C15": "cognitum/spatial_official_trackeval.py",
    "C16": "cognitum/physics_ode.py",
    "C17": "cognitum/temporal_statespace.py",
    "C18": "cognitum/adaptation_policy.py",
    "C19": "cognitum/topology_rips.py",
}

def inspect(root: Path) -> dict:
    """Source inventory only; neither CI success nor production readiness."""
    root = root.resolve()
    found = {}
    for component, name in REQUIRED.items():
        p = root / name
        found[component] = {
            "required_source": name,
            "source_present": p.is_file() and not p.is_symlink(),
        }
    missing = sorted(c for c, d in found.items() if not d["source_present"])
    return {
        "schema": "cognitum.integration-source-gate.v1",
        "status": "SOURCE_INVENTORY_INCOMPLETE" if missing else "SOURCE_INVENTORY_COMPLETE_ONLY",
        "tracked_components": len(REQUIRED),
        "source_present_count": len(REQUIRED)-len(missing),
        "missing": missing,
        "components": found,
        "release_ready": False,
        "lu_installed_host_roundtrip_verified": False,
        "note": (
            "No source-only gate can establish cross-platform native acceptance, "
            "a combined-tree integration pass, worker containment, or an "
            "authenticated installed Lu model-to-Cognitum roundtrip."
        ),
    }

def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--require-sources", action="store_true")
    args = parser.parse_args(argv)
    summary = inspect(args.root)
    payload = json.dumps(summary, sort_keys=True, indent=2)+"\n"
    print(payload, end="")
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")
    return 2 if args.require_sources and summary["missing"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
