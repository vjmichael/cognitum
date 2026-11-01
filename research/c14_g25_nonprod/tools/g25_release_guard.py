"""C14 G25 fail-closed *research* adapter for existing G25I conservative bounds.

No new interval estimator or causal identification method is introduced here.
This module only emits sensitivity intervals WITH user-declared, unverified
assumptions and never issues automatic causal-certification or production grants.
"""
from __future__ import annotations
import hashlib
import json
import math
import numbers
from pathlib import Path
import sys

import numpy as np

# Pinned standalone research baseline; avoids editing Cognitum production paths.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "baseline"))
from g25i_core import from_counts

VERSION = "C14-G25-guard-research-v1"
ALPHA = 0.05
MIN_ARM = 25  # prior G25I's review threshold; conservative reporting restriction


def strict_counts(value):
    """Accept only genuine nonnegative integer counts; never silently truncate."""
    a = np.asarray(value, dtype=object)
    if a.shape != (2, 2, 2):
        raise ValueError("expected exactly eight W,T,Y count cells")
    vals = []
    for x in a.flat:
        if isinstance(x, (bool, np.bool_)) or not isinstance(x, (int, np.integer)):
            raise ValueError("counts must be integers, not booleans or real-valued inputs")
        y = int(x)
        if y < 0 or y > 2**53:
            raise ValueError("count outside supported exact-integer range")
        vals.append(y)
    if sum(vals) == 0 or sum(vals) > 2**53:
        raise ValueError("sample size must be positive and exactly representable")
    return np.array(vals, dtype=np.int64).reshape(2, 2, 2)


def _gamma(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError("gamma must be an explicit real number")
    g = float(value)
    if not math.isfinite(g) or not 0 <= g <= 1:
        raise ValueError("gamma must lie in [0, 1]")
    return g


def _evidence_ok(evidence, gamma):
    if not isinstance(evidence, dict):
        return False
    for k in ("sampling_iid_supported", "consistency_supported", "measurement_validity_supported"):
        if evidence.get(k) is not True:
            return False
    justification = evidence.get("gamma_justification", "")
    if not isinstance(justification, str) or len(justification.strip()) < 12:
        return False
    if gamma == 0:
        exch = evidence.get("exchangeability_justification", "")
        if not isinstance(exch, str) or len(exch.strip()) < 12:
            return False
    return True


def _canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)


def report(counts, gamma, evidence=None):
    z = strict_counts(counts)
    g = _gamma(gamma)
    arm = z.sum(axis=2)
    # These are refusal semantics for the *reporting interface*, not mathematical
    # statements that a sufficiently large observed arm proves population overlap.
    if int(arm.min()) == 0:
        status, reason = "blocked_missing_observed_arm", "At least one observed W/T arm is absent."
    elif int(arm.min()) < MIN_ARM:
        status, reason = "blocked_sparse_observed_arm", "Small observed W/T arms require independent review."
    elif not _evidence_ok(evidence, g):
        status, reason = "blocked_missing_assumption_evidence", "Assumption justification is missing or incomplete."
    else:
        status, reason = "conditional_sensitivity_report_only", "Gamma and causal assumptions are analyst-declared, not empirically certified."
    outer = None
    identified = None
    if status == "conditional_sensitivity_report_only":
        r = from_counts(z, g, alpha=ALPHA)
        if r["status"] != "computed_conditional_on_gamma":
            raise AssertionError("unexpected baseline release status")
        outer = r["outer95"]
        identified = r["identified"]
    counts_bytes = _canonical(z.tolist()).encode()
    payload = {
        "schema_version": 1,
        "method_id": VERSION,
        "sample_size": int(z.sum()),
        "min_observed_arm_count": int(arm.min()),
        "counts_sha256": hashlib.sha256(counts_bytes).hexdigest(),
        "gamma_analyst_supplied": g,
        "alpha_nominal": ALPHA,
        "status": status,
        "reason": reason,
        "identified_set_plugin": identified,
        "identified_set_outer95_conditional": outer,
        "automatic_causal_certification": False,
        "production_estimator_promotion": False,
        "unmeasured_confounding_excluded": False,
        "identification_verified_from_data": False,
        "scientific_scope": "iid binary W,T,Y; conditional on analyst-justified Gamma and consistency/measurement assumptions",
        "not_a_proof_of": ["absence_of_hidden_confounding", "validity_of_gamma", "generalized_CI_calibration"],
    }
    return {**payload, "receipt_sha256": hashlib.sha256(_canonical(payload).encode()).hexdigest()}


def replay_audit(receipt, counts, gamma, evidence=None):
    """Recompute full semantics, not just a forgeable checksum."""
    if not isinstance(receipt, dict):
        return False
    try:
        expected = report(counts, gamma, evidence)
        return _canonical(receipt) == _canonical(expected)
    except (TypeError, ValueError, OverflowError, AssertionError):
        return False
