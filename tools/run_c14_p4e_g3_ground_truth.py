"""C14 P4E G3: reproducible *genuine-Tigramite* synthetic stress evaluation.

This is benchmark/test tooling, not a Lu-authenticated host. Simulations have
known source equations; observational causal assumptions are not verified by the
algorithms, and test-set detection frequencies are not calibrated probabilities.
No user data or third-party package is written to the checkpoint.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
from importlib.metadata import PackageNotFoundError, version

import numpy as np

from cognitum.causal_tigramite_backend import VERSION, _compute_worker, verify_temporal_discovery_receipt
from cognitum.proto import causal_temporal_discovery_pb2 as td
from cognitum.proto import causal_temporal_diagnostics_pb2 as p4c

METHODS = {"PCMCI": td.TD_PCMCI_LAGGED, "PCMCI+": td.TD_PCMCI_PLUS}
SCENARIOS = ("direct_lag", "independent", "latent_common_cause", "structural_change")
DEFAULT_SEEDS = (13, 29, 43, 61, 83)
DEFAULT_SIZES = (160, 320)
ALPHA = 0.05


def make_series(scenario: str, rows: int, seed: int) -> np.ndarray:
    """Generate X,Y with explicit equation ground truth (burn-in discarded)."""
    if scenario not in SCENARIOS or not 100 <= rows <= 500 or seed < 1:
        raise ValueError("INVALID_G3_GENERATOR_PARAMETERS")
    rng = np.random.default_rng(seed)
    burn = 150
    e = rng.normal(size=(rows + burn, 3))
    x = np.zeros(rows + burn, dtype=np.float64)
    y = np.zeros(rows + burn, dtype=np.float64)
    hidden = np.zeros(rows + burn, dtype=np.float64)
    for t in range(1, rows + burn):
        if scenario == "latent_common_cause":
            hidden[t] = 0.65 * hidden[t-1] + e[t, 2]
            x[t] = 0.4 * x[t-1] + 0.8 * hidden[t-1] + e[t, 0]
            y[t] = 0.4 * y[t-1] + 0.8 * hidden[t-1] + e[t, 1]
        else:
            x[t] = 0.55 * x[t-1] + e[t, 0]
            direct_effect = 0.85 if scenario == "direct_lag" else 0.0
            if scenario == "structural_change":
                direct_effect = 0.85 if t - burn < rows // 2 else -0.85
            y[t] = 0.35 * y[t-1] + direct_effect * x[t-1] + e[t, 1]
    return np.stack((x[burn:], y[burn:]), axis=1)


def make_request(scenario: str, rows: int, seed: int, mode: int) -> bytes:
    arr = make_series(scenario, rows, seed)
    obs = p4c.TemporalDiagnosticRequest(
        schema_version=1, trace_id='c14-p4e-g3-synthetic',
        variable_ids=['X', 'Y'], declared_interval_ms=250, max_lag=1,
        familywise_alpha=0.05, timeout_ms=10000)
    for idx, (x, y) in enumerate(arr):
        obs.observations.add(timestamp_ms=10000 + idx * 250, values=[float(x), float(y)])
    req = td.TemporalDiscoveryRequest(
        schema_version=1, samples=obs, mode=mode, tau_max=1,
        pc_alpha=ALPHA, timeout_ms=30000, seed=seed,
        stationarity_assumption_acknowledged=True)
    return req.SerializeToString(deterministic=True)


def score_candidate(raw: bytes, reply: bytes, scenario: str):
    result = td.TemporalDiscoveryResult.FromString(reply)
    check = verify_temporal_discovery_receipt(raw, reply)
    if result.status != td.TD_CANDIDATE or not check.request_bound_structure_checked:
        raise ValueError(f"UNVERIFIED_G3_RESULT:{result.reason_code}")
    if result.causal_assumptions_verified or result.causal_directions_proven or check.independent_causal_proof:
        raise ValueError("UNJUSTIFIED_CAUSAL_PROOF_CLAIM")
    lagged = {(x.source, x.target, x.lag) for x in result.links
              if x.lag == 1 and x.source != x.target}
    # Only direct_lag and independent have valid 'full observed causal graph'
    # assumptions. Stress scenarios must not be counted as primary precision.
    if scenario == 'direct_lag':
        truth = {(0, 1, 1)}
    elif scenario == 'independent':
        truth = set()
    else:
        truth = None
    if truth is None:
        return {"candidate_cross_links": len(lagged),
                "x_to_y_detected": (0, 1, 1) in lagged,
                "y_to_x_detected": (1, 0, 1) in lagged}
    return {"tp": len(lagged & truth), "fp": len(lagged - truth),
            "fn": len(truth - lagged), "tn": 2 - len(lagged | truth),
            "candidate_cross_links": len(lagged),
            "x_to_y_detected": (0, 1, 1) in lagged,
            "y_to_x_detected": (1, 0, 1) in lagged}


def evaluate(seeds=DEFAULT_SEEDS, sizes=DEFAULT_SIZES, scenarios=SCENARIOS, methods=METHODS):
    try:
        installed = version('tigramite')
    except PackageNotFoundError as exc:
        raise RuntimeError("GENUINE_TIGRAMITE_REQUIRED") from exc
    if installed != VERSION:
        raise RuntimeError("TIGRAMITE_UNAPPROVED_VERSION:" + installed)
    cases = []
    for rows in sizes:
        for seed in seeds:
            for scenario in scenarios:
                for method, mode in methods.items():
                    raw = make_request(scenario, rows, seed, mode)
                    start = time.perf_counter()
                    reply = _compute_worker(raw)
                    elapsed_ms = round(1000 * (time.perf_counter() - start), 3)
                    scored = score_candidate(raw, reply, scenario)
                    cases.append({"scenario": scenario, "method": method,
                                  "rows": rows, "seed": seed,
                                  "request_sha256": hashlib.sha256(raw).hexdigest(),
                                  "wall_ms_observed": elapsed_ms,
                                  **scored})
    summaries = []
    for rows in sizes:
        for method in methods:
            for scenario in scenarios:
                group = [c for c in cases if c['rows'] == rows and c['method'] == method
                         and c['scenario'] == scenario]
                summary = {"rows": rows, "method": method, "scenario": scenario,
                           "runs": len(group),
                           "x_to_y_detection_count": sum(x['x_to_y_detected'] for x in group),
                           "y_to_x_detection_count": sum(x['y_to_x_detected'] for x in group),
                           "wall_ms_median_observed": sorted(x['wall_ms_observed'] for x in group)[len(group)//2]}
                if scenario in ("direct_lag", "independent"):
                    for name in ("tp", "fp", "fn", "tn"):
                        summary[name] = sum(x[name] for x in group)
                    if scenario == "direct_lag":
                        summary['lagged_edge_recall'] = summary['tp'] / max(1, summary['tp'] + summary['fn'])
                        summary['lagged_edge_precision'] = summary['tp'] / max(1, summary['tp'] + summary['fp'])
                    else:
                        summary['at_least_one_cross_edge_count'] = sum(x['candidate_cross_links'] > 0 for x in group)
                else:
                    summary['assumption_violations_present'] = (
                        'hidden confounding' if scenario == 'latent_common_cause'
                        else 'nonstationary time-varying structural equation')
                summaries.append(summary)
    return {
        "name": "C14 P4E G3 Tigramite synthetic ground truth and assumption stress",
        "backend": "tigramite", "version": installed,
        "method_significance_policies": {"PCMCI": "FDR_BH", "PCMCI+": "uncorrected"},
        "source_archive_sha256": "427e01cc18b75b9bb575537fc3a03ebbd6ee8c8fc973616328725c851e63eff8",
        "python_executable": Path(sys.executable).name,
        "python_version": platform.python_version(),
        "numpy": np.__version__,
        "seeds": list(seeds), "sizes": list(sizes), "alpha": ALPHA,
        "case_count": len(cases), "summaries": summaries,
        "cases": cases,
        "interpretation": [
            "Only within-fixture candidate-edge recovery is measured; no real-world causality is established.",
            "No calibrated FDR, power, model-size scaling, or OS security certification is implied.",
            "Hidden-confounding and structural-change scenarios violate standard causal assumptions and are reported separately, not pooled into edge precision/recall.",
            "PCMCI BH-adjusted and PCMCI+ uncorrected significance policies must not be interpreted as equivalent.",
            "All invocation uses a local Python test harness, not authenticated Lu or Windows containment.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--quick', action='store_true', help='one seed and size for development smoke only')
    args = parser.parse_args()
    data = evaluate(seeds=(DEFAULT_SEEDS[0],), sizes=(DEFAULT_SIZES[0],)) if args.quick else evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')
    print('G3_CASES', data['case_count'])
    for entry in data['summaries']:
        print(entry['rows'], entry['scenario'], entry['method'], 'X->Y',
              entry['x_to_y_detection_count'], '/', entry['runs'],
              'Y->X', entry['y_to_x_detection_count'])

if __name__ == '__main__':
    main()
