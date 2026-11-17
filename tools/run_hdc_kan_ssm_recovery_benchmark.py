"""Cross-family recovery audit benchmark with SEPARATE task-specific outcomes.

HDC retrieval, KAN RBF inference and SSM recurrence have different tasks,
so never rank their absolute times/accuracy as if they were interchangeable.
"""
from __future__ import annotations
import json
from statistics import median
from time import perf_counter
import numpy as np

from cognitum.research.hdc_recovered.models import MODEL_REGISTRY
from cognitum.research.hdc_recovered.memory import Bank
from cognitum.research.kan_optional import _load
from cognitum.research.ssm_recovered import DiagonalSSM
from tests.test_research_optional import kan_artifact


def hdc_retrieval():
    rows = []
    for family in ("bsc", "map", "fhrr", "hrr"):
        m = MODEL_REGISTRY[family](512, seed=4)
        rng = np.random.default_rng(5)
        corpus = m.atomic(64, rng)
        bank = Bank(m, corpus, list(range(64)))
        hits = 0
        durations = []
        for j in range(48):
            key = j % 64
            cue = m.perturb(corpus[key], "bitflip", 0.1, rng)
            start = perf_counter()
            predicted = bank.cleanup(cue)
            durations.append((perf_counter() - start) * 1000)
            hits += int(predicted == key)
        rows.append({
            "variant": family,
            "task": "top1_noisy_item_cleanup_64x512",
            "top1_correct": hits,
            "trials": 48,
            "median_ms": round(median(durations), 5),
            "vector_bytes": m.bytes_per_hv(),
        })
    return rows


def kan_inference():
    model = _load(kan_artifact())
    timings = []
    predictions = []
    for i in range(48):
        x = np.array([[float((i % 9) - 4) / 4]], dtype=np.float32)
        t0 = perf_counter()
        pred = model(x)
        timings.append((perf_counter() - t0) * 1000)
        if not np.isfinite(pred).all():
            raise AssertionError("KAN produced non-finite output")
        predictions.append(float(pred[0, 0]))
    # This 1-input checkpoint is a controlled fixture, not learned model
    # performance or any comparison against a matched trained MLP.
    return {
        "variant": "K4_numpy_rbf_fixture",
        "task": "bounded_single_sample_checkpoint_inference",
        "trials": len(timings),
        "finite_outputs": len(predictions),
        "median_ms": round(median(timings), 5),
        "learned_generalization_claim": False,
    }


def ssm_recurrence():
    params = {"a":[0.9,0.7],"b":[[0.2],[0.4]],
              "c":[[0.3,0.8]],"d":[[0.1]]}
    model = DiagonalSSM.from_mapping(params)
    A = np.diag(params["a"])
    B = np.array(params["b"])
    C = np.array(params["c"])
    D = np.array(params["d"])
    timings=[]
    maximum=0.0
    for seed in range(48):
        g = np.random.default_rng(seed)
        input_values = [[float(z)] for z in g.normal(size=32)]
        state = np.zeros(2)
        baseline = []
        for item in input_values:
            v = np.asarray(item)
            state = A @ state + B @ v
            baseline.append((C @ state + D @ v).tolist())
        start=perf_counter()
        result=model.scan(input_values)
        timings.append((perf_counter()-start)*1000)
        maximum=max(maximum, float(np.max(np.abs(
            np.asarray(result["outputs"]) - np.asarray(baseline)
        ))))
    if maximum > 1e-10:
        raise AssertionError("SSM numerical recurrence parity failed")
    return {
        "variant": "diagonal_linear_reference",
        "task": "32_step_state_scan_against_independent_numpy",
        "trials": len(timings),
        "max_abs_error": maximum,
        "median_ms": round(median(timings), 5),
        "trained_selective_model_claim": False,
    }


def run():
    return {
        "classification": "RESEARCH_REFERENCE_ONLY",
        "hardware": "current CI runner CPU; no ARM power measurement",
        "not_comparable_across_families": True,
        "hdc": hdc_retrieval(),
        "kan": kan_inference(),
        "ssm": ssm_recurrence(),
        "next_gate": "real held-out matched baselines and learned KAN/selective SSM"
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
