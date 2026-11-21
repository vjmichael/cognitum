"""BENCH-02-R3 preregistered, prediction-free hourly METAR cohort constructor.

Original source bytes are verified, but AWC receiptTime is not authenticated
public availability. Strict first-capture-as-of and retrospective receipt proxy
are deliberately separate. No numerical model is imported or fitted here.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math

HOUR = 3_600_000
ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs/research/orcgraph/ORCH01E_BENCH02_R3_PREREG.json"

class Refusal(ValueError):
    pass

def require(value, why):
    if not value:
        raise Refusal(why)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")

def lock():
    original = PREREG.read_bytes()
    spec = json.loads(original)
    assert_spec(spec)
    return spec, sha256(original).hexdigest()

def assert_spec(p):
    require(p["schema"] == "cognitum.orc.bench02.r3.preregistered.v1", "protocol identity")
    require(p["independent_stations_in_fixed_order"] == ["KSEA", "KDEN", "KATL"], "station mutation")
    require(p["previously_inspected_regression_station_excluded"] == "KMCI", "control mutated")
    require(p["forecast_horizons_hours"] == [1, 3, 6], "horizon mutation")
    require(p["history_feature_lags_hours"] == [0, 1, 3, 6, 24], "feature mutation")
    require(p["fixed_hourly_buckets"] == 192 and
            p["chronological_folds"] == {"train_hours": 115,
                                         "calibration_hours": 38, "test_hours": 39},
            "fold mutation")
    require(p["maximum_source_rows_per_station_exclusive"] == 400 and
            p["source_window_request_hours"] == 240, "response threshold mutation")
    require(p["historical_provider_receipt_is_public_availability_proof"] is False and
            p["no_model_fitting_or_test_based_selection_in_R3"] is True and
            p["no_site_replacement_for_gaps_or_losses"] is True, "scientific protection weakened")


def as_ms(value):
    require(type(value) is str and value.strip(), "missing receipt timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as ex:
        raise Refusal("invalid provider UTC receipt timestamp") from ex
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None,
            "unqualified receipt timezone")
    return int(parsed.astimezone(timezone.utc).timestamp() * 1000)


def source_rows(raw: bytes, station: str, *, capture_start_ms: int,
                capture_end_ms: int, sha256_pin: str, first_seen_ms: int | None = None):
    """Validate exact received provider bytes; preserve original row order/versions."""
    spec, _ = lock()
    require(station in spec["independent_stations_in_fixed_order"],
            "site not preregistered; previous KMCI control ineligible")
    require(type(raw) is bytes and 2 <= len(raw) <= spec["maximum_json_bytes_per_station"],
            "truncated or oversized source bytes")
    require(type(sha256_pin) is str and sha256(raw).hexdigest() == sha256_pin,
            "original source SHA mismatch")
    require(type(capture_start_ms) is int and type(capture_end_ms) is int and
            0 < capture_start_ms <= capture_end_ms, "invalid capture clock")
    if first_seen_ms is None:
        first_seen_ms = capture_end_ms
    require(type(first_seen_ms) is int and first_seen_ms >= capture_start_ms and
            first_seen_ms <= capture_end_ms, "forged first-seen claim")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as ex:
        raise Refusal("not original JSON UTF-8") from ex
    require(type(parsed) is list and 0 < len(parsed) < 400,
            "empty or 400-row source may be truncated")
    accepted = []
    for position, row in enumerate(parsed):
        require(type(row) is dict and row.get("icaoId") == station,
                "original station label mismatch")
        event = row.get("obsTime")
        require(type(event) is int and 946684800 <= event <= 4102444800,
                "unqualified source observation epoch")
        observed_ms = event * 1000
        receipt_ms = as_ms(row.get("receiptTime"))
        require(observed_ms <= receipt_ms <= capture_end_ms,
                "observation/receipt/fetch clock contradiction")
        report = row.get("rawOb")
        require(type(report) is str and station in report.split(),
                "raw report station identity mismatch")
        value = row.get("temp")
        require(value is None or (type(value) in (int, float) and
                math.isfinite(value) and value > -273.15),
                "invalid original Celsius/Kelvin")
        accepted.append({
            "source_row": position, "station": station,
            "original_record_sha256": sha256(canonical(row)).hexdigest(),
            "observed_ms": observed_ms, "receipt_ms": receipt_ms,
            "first_seen_ms": first_seen_ms,
            "hour_bucket_ms": (observed_ms // HOUR) * HOUR,
            "has_temperature": value is not None,
            "temperature_kelvin": (float(value) + 273.15) if value is not None else None,
        })
    return accepted


def build_site(raw: bytes, station: str, *, capture_start_ms: int,
               capture_end_ms: int, sha256_pin: str):
    spec, prereg_sha256 = lock()
    rows = source_rows(raw, station, capture_start_ms=capture_start_ms,
                       capture_end_ms=capture_end_ms, sha256_pin=sha256_pin)
    end_ms = (capture_start_ms // HOUR) * HOUR - 2 * HOUR
    begin_ms = end_ms - 192 * HOUR
    require(end_ms < capture_start_ms and begin_ms > 0, "frozen time window invalid")
    bins = defaultdict(list)
    outside = 0
    for item in rows:
        if begin_ms <= item["hour_bucket_ms"] < end_ms:
            bins[item["hour_bucket_ms"]].append(item)
        else:
            outside += 1
    statuses, chosen = [], {}
    for i in range(192):
        bucket = begin_ms + i * HOUR
        versions = bins[bucket]
        if not versions:
            status = "missing_hour"
        elif len(versions) != 1:
            status = "ambiguous_multiple_or_corrected_reports"
        elif not versions[0]["has_temperature"]:
            status = "missing_temperature"
        else:
            status = "single_observation"
            chosen[i] = versions[0]
        statuses.append(status)
    boundaries = (("train", 0, 115), ("calibration", 115, 153),
                  ("test", 153, 192))
    horizons = []
    for horizon in spec["forecast_horizons_hours"]:
        folds = {}
        for label, left, right in boundaries:
            counts = Counter()
            retro, first_capture = [], []
            for origin_i in range(left, right):
                target_i = origin_i + horizon
                if target_i >= right:
                    counts["target_crosses_fold"] += 1
                    continue
                if target_i not in chosen:
                    counts["target_" + statuses[target_i]] += 1
                    continue
                origin_ms = begin_ms + (origin_i + 1) * HOUR
                feature_indices = [origin_i - lag for lag in
                                   spec["history_feature_lags_hours"]]
                if any(j < 0 for j in feature_indices):
                    counts["insufficient_history"] += 1
                    continue
                bad = next((statuses[j] for j in feature_indices
                            if j not in chosen), None)
                if bad is not None:
                    counts["feature_" + bad] += 1
                    continue
                latest_receipt = max(chosen[j]["receipt_ms"] for j in feature_indices)
                if latest_receipt > origin_ms:
                    counts["feature_provider_receipt_late"] += 1
                    continue
                pair = [origin_ms, begin_ms + (target_i + 1) * HOUR]
                retro.append(pair)
                if max(chosen[j]["first_seen_ms"] for j in feature_indices) > origin_ms:
                    counts["feature_first_capture_too_late"] += 1
                    continue
                first_capture.append(pair)
            counts["retrospective_receipt_proxy_eligible"] = len(retro)
            counts["first_capture_bounded_eligible"] = len(first_capture)
            folds[label] = {
                "all_origin_hours": right - left,
                "reason_counts": dict(sorted(counts.items())),
                "retrospective_cohort_sha256": sha256(canonical(retro)).hexdigest(),
                "first_capture_cohort_sha256": sha256(canonical(first_capture)).hexdigest(),
                "retrospective_origin_target_clock_pairs": retro,
                "first_capture_origin_target_clock_pairs": first_capture,
            }
        horizons.append({"forecast_horizon_hours": horizon, "folds": folds})
    return {
        "schema": "cognitum.orc.bench02.r3.cohort.v1",
        "station": station, "provenance_type": "AWC_HISTORIC_SOURCE_WITH_UNVERIFIED_PUBLICATION",
        "original_source_sha256": sha256_pin,
        "original_source_rows": len(rows), "out_of_locked_window_rows": outside,
        "preregistered_protocol_sha256": prereg_sha256,
        "original_capture_started_ms": capture_start_ms,
        "original_capture_finished_ms": capture_end_ms,
        "source_clock_end_exclusive_ms": end_ms,
        "source_clock_start_inclusive_ms": begin_ms,
        "fold_hours": [115, 38, 39], "hours_with_each_status": dict(sorted(Counter(statuses).items())),
        "horizons": horizons,
        "all_targets_kept_private_from_model_selection": True,
        "real_historical_publication_attested": False,
        "production_admission_authorized": False,
        "no_fitting_or_scoring_performed": True,
    }


def preregistration_summary():
    spec, digest = lock()
    return {
        "schema": spec["schema"], "preregistered_sha256": digest,
        "stations": spec["independent_stations_in_fixed_order"],
        "horizons": spec["forecast_horizons_hours"],
        "fold_hours": [115, 38, 39],
        "source_acquisition_performed": False,
        "forecast_models_fitted": False,
        "heldout_scores_computed": False,
        "strict_causal_claim_approved": False,
    }

if __name__ == "__main__":
    print(json.dumps(preregistration_summary(), sort_keys=True, indent=2))
