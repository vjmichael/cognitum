"""POST-NATIVE-05: explicitly bounded, non-authorizing publisher-separated dynamics tests.

Do not reinterpret these observational forecasts as causal laws. Do not resample
uneven observations to make the existing fixed-step HDC/KAN/SSM appear qualified.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
from datetime import datetime, timezone
from typing import Any

import numpy as np

SOURCES = {
    "noaa_partner_water_level": {
        "blob": "8421af63a839c767555a53af74b71106ee68241e",
        "publisher": "NOAA-CO-OPS",
        "origin": "RA partner station supplied to NOAA; not independently NOAA-signed",
        "unit": "water-level units not independently verified",
        "horizons": (300, 1800, 7200),  # 5, 30, 120 minutes, NOT sample steps
        "lags": (300, 1800),
        "block": 24,
        "period": 300,
        "train_min": 500,
    },
    "usgs_natural_flow": {
        "blob": "2f986df07dce96b800829856e751b247e4179aaf",
        "publisher": "DOI-USGS",
        "origin": "Colorado River reconstructed natural flow (not raw discharge sensor)",
        "unit": "original source units not independently verified",
        "horizons": (1, 3, 5),  # years
        "lags": (1, 2),
        "block": 4,
        "period": 1,
        "train_min": 40,
    },
}


def require(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError(why)


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


def ingest(name: str, raw: bytes) -> dict[str, Any]:
    """Reject source drift and conflicting duplicate timestamps without repairing data."""
    require(name in SOURCES and type(raw) is bytes, "unknown publisher dataset/type")
    spec = SOURCES[name]
    require(git_blob(raw) == spec["blob"], "publisher file byte identity")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    require(len(rows) > 100, "publisher source empty")
    if name == "noaa_partner_water_level":
        require(rows[0] == ["time", "val"], "NOAA schema changed")
        pairs = [(int(datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S")
                      .replace(tzinfo=timezone.utc).timestamp()), float(r[1]))
                 for r in rows[1:] if r]
    else:
        require(rows[0] == ["Year", "Natural Flow above Lees Ferry", "Natural Flow above Imperial"], "USGS schema changed")
        pairs = [(int(r[0]), float(r[1])) for r in rows[1:] if r]
    require(all(math.isfinite(v) for _, v in pairs), "missing/invalid primary target")
    require(all(pairs[i][0] <= pairs[i + 1][0] for i in range(len(pairs) - 1)),
            "chronological source monotonicity")
    counts = {}
    for t, _ in pairs:
        counts[t] = counts.get(t, 0) + 1
    conflicts = sum(count > 1 for count in counts.values())
    # An ambiguous repeated instant is excluded entirely, never averaged or chosen.
    unique = [(t, v) for t, v in pairs if counts[t] == 1]
    t = np.asarray([p[0] for p in unique], dtype=np.int64)
    y = np.asarray([p[1] for p in unique], dtype=np.float64)
    require(len(t) > 90 and bool(np.all(np.diff(t) > 0)), "valid independent timestamps")
    irregular = int(np.sum(np.diff(t) != spec["period"]))
    return {
        "name": name, "times": t, "values": y,
        "source_git_blob": spec["blob"], "publisher": spec["publisher"],
        "quarantined_conflicting_instants": conflicts,
        "quarantined_rows": len(pairs) - len(unique),
        "irregular_intervals": irregular,
        "observations": len(y), "unit": spec["unit"],
        "original_records": len(pairs),
    }


def regions(n: int) -> tuple[tuple[int, int], ...]:
    require(n >= 100, "inadequate observed series")
    e = (0, int(n * .60), int(n * .80), n)
    return tuple((e[i], e[i + 1]) for i in range(3))


def origin_pairs(s: dict, start: int, stop: int, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    """Only timestamps actually present; history and target must stay inside fold."""
    spec = SOURCES[s["name"]]
    t = s["times"]
    lookup = {int(z): i for i, z in enumerate(t)}
    origins, targets = [], []
    for i in range(start, stop):
        now = int(t[i])
        target = lookup.get(now + horizon)
        if target is None or not (start <= target < stop):
            continue
        if all((j := lookup.get(now - lag)) is not None and start <= j < stop for lag in spec["lags"]):
            origins.append(i)
            targets.append(target)
    return np.asarray(origins, dtype=np.int64), np.asarray(targets, dtype=np.int64)


def features(s: dict, origin: np.ndarray, horizon: int) -> np.ndarray:
    """Origin-time observations and known calendar phase; never future sensor values."""
    spec = SOURCES[s["name"]]
    t = s["times"]
    y = s["values"]
    loc = {int(z): i for i, z in enumerate(t)}
    X = [y[origin]]
    for lag in spec["lags"]:
        X.append(y[[loc[int(z) - lag] for z in t[origin]]])
    if s["name"].startswith("noaa"):
        target_time = t[origin].astype(float) + horizon
        for hours in (12.4206, 12.0, 23.9345, 25.8193):
            phase = 2 * np.pi * (target_time % (hours * 3600)) / (hours * 3600)
            X.extend((np.sin(phase), np.cos(phase)))
    else:
        X.append((t[origin] - 1906) / 110.0)
    return np.column_stack(X)


def ridge_fit(x: np.ndarray, y: np.ndarray, strength: float = 10.0) -> dict:
    require(len(x) >= 30 and len(x) == len(y), "train-only ridge sample budget")
    mean = x.mean(axis=0)
    sd = x.std(axis=0)
    sd[sd < 1e-10] = 1
    z = np.column_stack(((x - mean) / sd, np.ones(len(x))))
    penalty = np.eye(z.shape[1]) * strength
    penalty[-1, -1] = 0
    coef = np.linalg.solve(z.T @ z + penalty, z.T @ y)
    return {"mean": mean, "sd": sd, "coef": coef}


def ridge_forecast(fit: dict, x: np.ndarray) -> np.ndarray:
    return np.column_stack(((x - fit["mean"]) / fit["sd"], np.ones(len(x)))) @ fit["coef"]


def harmonic_features(times: np.ndarray) -> np.ndarray:
    x = []
    for hours in (12.4206, 12.0, 23.9345, 25.8193):
        phase = 2 * np.pi * (times.astype(float) % (hours * 3600)) / (hours * 3600)
        x.extend((np.sin(phase), np.cos(phase)))
    return np.column_stack(x)


def metrics(actual: np.ndarray, forecast: np.ndarray) -> dict:
    require(len(actual) > 0 and np.isfinite(actual).all() and np.isfinite(forecast).all(), "finite scoring")
    d = actual - forecast
    return {"n": len(d), "mae": float(np.mean(np.abs(d))),
            "rmse": float(np.sqrt(np.mean(d * d)))}


def consecutive_blocks(errors: np.ndarray, times: np.ndarray, step: int, block: int) -> np.ndarray:
    """Non-overlapping runs of consecutive *actual* forecast-origin times."""
    require(len(errors) == len(times) and len(times) > 0
            and bool(np.all(np.diff(times) > 0)), "ordered block scores")
    ends = np.r_[0, np.flatnonzero(np.diff(times) != step) + 1, len(times)]
    blocks = [errors[a + off:a + off + block]
              for a, b in zip(ends[:-1], ends[1:])
              for off in range(0, b - a - block + 1, block)]
    return np.stack(blocks) if blocks else np.empty((0, block))


def block_diagnostics(cal_error: np.ndarray, cal_times: np.ndarray,
                      test_error: np.ndarray, test_times: np.ndarray,
                      step: int, block: int, seed: int = 505) -> dict:
    """Descriptive block-max calibration only; dependence guarantee explicitly denied."""
    cal = consecutive_blocks(np.abs(cal_error), cal_times, step, block)
    test = consecutive_blocks(np.abs(test_error), test_times, step, block)
    if len(cal) < 20 or len(test) < 10:
        return {"status": "REFUSED_INSUFFICIENT_BLOCKS",
                "calibration_blocks": len(cal), "test_blocks": len(test),
                "distribution_free_coverage": False}
    k = math.ceil((len(cal) + 1) * .9) - 1
    if k >= len(cal):
        return {"status": "REFUSED_FINITE_RANK", "calibration_blocks": len(cal),
                "test_blocks": len(test), "distribution_free_coverage": False}
    radius = float(np.sort(cal.max(axis=1))[k])
    hit = np.abs(test_error) <= radius
    n = len(hit)
    # Never shift the fit/calibration data. Perturbed future observations are
    # a synthetic counterexample, NOT actual measured hydrodynamics.
    shifted = np.abs(test_error + 3 * radius) <= radius
    return {"status": "DESCRIPTIVE_ONLY", "nominal": .9, "radius": radius,
            "calibration_blocks": len(cal), "test_blocks": len(test),
            "empirical_origin_coverage": float(hit.mean()),
            "simultaneous_test_block_coverage": float((test.max(axis=1) <= radius).mean()),
            "first_half": float(hit[:n // 2].mean()),
            "second_half": float(hit[n // 2:].mean()),
            "synthetic_plus_3radius_coverage": float(shifted.mean()),
            "distribution_free_coverage": False}


def missingness_sensitivity(actual: np.ndarray, prediction: np.ndarray) -> dict:
    """Counterfactual observation-selection audit, not forecasting with future targets."""
    n = len(actual)
    if n <= 20:
        return {"status": "REFUSED_INSUFFICIENT_TEST_OBSERVATIONS",
                "test_origins": n, "full_case": metrics(actual, prediction),
                "missingness_mechanisms_are_counterfactual": True}
    full = metrics(actual, prediction)
    # Simulated repeated sensor outages; explicit nonrandom high-target censoring.
    periodic = np.arange(n) % 101 >= 24
    high = actual < np.quantile(actual, .8)
    require(periodic.any() and high.any(), "missingness mask")
    return {"full_case": full, "simulated_outage": metrics(actual[periodic], prediction[periodic]),
            "simulated_high_target_censoring": metrics(actual[high], prediction[high]),
            "outage_fraction": float(1 - periodic.mean()),
            "high_target_censored_fraction": float(1 - high.mean()),
            "missingness_mechanisms_are_counterfactual": True}


def evaluate(s: dict) -> dict:
    spec = SOURCES[s["name"]]
    folds = regions(len(s["times"]))
    results = {}
    for horizon in spec["horizons"]:
        origins, targets = [], []
        for lo, hi in folds:
            o, z = origin_pairs(s, lo, hi, horizon)
            origins.append(o)
            targets.append(z)
        require(min(map(len, origins)) > 10 and len(origins[0]) >= spec["train_min"],
                "chronological eligible observation budget")
        yt = s["values"]
        xtr = features(s, origins[0], horizon)
        xcal = features(s, origins[1], horizon)
        xte = features(s, origins[2], horizon)
        fit = ridge_fit(xtr, yt[targets[0]])
        predictions = {}
        for fold_name, idx, tar, xx in (("cal", 1, targets[1], xcal), ("test", 2, targets[2], xte)):
            base = {
                "persistence": yt[origins[idx]],
                "direct_ridge": ridge_forecast(fit, xx),
                "train_mean": np.full(len(tar), float(np.mean(yt[targets[0]]))),
            }
            if s["name"].startswith("noaa"):
                harmonic = ridge_fit(harmonic_features(s["times"][origins[0]]),
                                     yt[origins[0]], strength=1.)
                base["harmonic_tide"] = ridge_forecast(
                    harmonic, harmonic_features(s["times"][tar]))
            predictions[fold_name] = base
        cal = {k: metrics(yt[targets[1]], v) for k, v in predictions["cal"].items()}
        selected = min(cal, key=lambda name: cal[name]["mae"])
        test = {k: metrics(yt[targets[2]], v) for k, v in predictions["test"].items()}
        err_cal = yt[targets[1]] - predictions["cal"][selected]
        err_test = yt[targets[2]] - predictions["test"][selected]
        uncertainty = block_diagnostics(err_cal, s["times"][origins[1]],
                                        err_test, s["times"][origins[2]],
                                        spec["period"], spec["block"])
        missing = missingness_sensitivity(yt[targets[2]], predictions["test"][selected])
        results[str(horizon)] = {
            "horizon_in_seconds_or_years": horizon,
            "train_origins": len(origins[0]), "cal_origins": len(origins[1]),
            "test_origins": len(origins[2]),
            "calibration_selected_model": selected,
            "calibration_metrics": cal, "test_metrics": test,
            "dependence_calibration": uncertainty, "missingness": missing,
            "chosen_using_test_targets": False,
        }
    # Original fixed-step architecture cannot be legitimately treated as an
    # irregular-timestamp model; annual USGS sample is underpowered for KAN.
    hybrid = ("REFUSED_IRREGULAR_DELTA_T_NEEDS_NATIVE_TIME_AWARE_MODEL"
              if s["irregular_intervals"] else
              "REFUSED_INSUFFICIENT_INDEPENDENT_TRAINING_SAMPLES")
    return {
        "dataset": s["name"], "publisher": s["publisher"],
        "origin": SOURCES[s["name"]]["origin"],
        "source_git_blob": s["source_git_blob"],
        "raw_observations": s["original_records"],
        "admitted_observations": s["observations"],
        "quarantined_conflicting_instants": s["quarantined_conflicting_instants"],
        "irregular_intervals": s["irregular_intervals"],
        "unit": s["unit"], "outcomes": results,
        "hdc_kan_ssm_native_falsification": hybrid,
        "out_of_domain_source_specific": True,
        "missing_data_imputed": False, "physical_law_discovered": False,
        "conditional_coverage_guaranteed": False, "execution_authorized": False,
        "scientifically_qualified_hybrid_superiority": False,
    }
