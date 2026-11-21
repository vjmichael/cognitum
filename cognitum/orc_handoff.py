"""ORCH-01C — trusted host scientific-data handoffs to existing COG-06/MEL.

Inert compilation only. Does not issue grants, install plugins, dispatch work,
run a scheduler, or authenticate upstream instruments. The trusted host must
recheck source freshness and permissions at execution; MEL admission performs
per-worker authorization, checkpoint pinning, cancellation and revocation.

No trained forecasting model is created here. KAN requires a host-reviewed
checkpoint; VFA evaluates a host-provided function; classical Kalman uses the
existing C17 CPU filter. They are not equivalent forecasting comparators.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite

from . import orc_science_data as d
from .cooperative import (Plan as CpuPlan, Step, SourceStamp, plan_digest)
from .cooperative_cpu import ROUTES, type_url, wire
from .mel import admission as a, cooperation as g, native as n
from .mel import model_engines as m, verified_graph as vg
from .proto import temporal_practical_pb2 as temporal
from .temporal_statespace import TemporalModel, TemporalSample, TemporalSequence, validate

_UNIT_TOKEN = {"m": "m", "m3/s": "m3_per_s", "K": "K", "1": "dimensionless"}
_FEATURE_AXES = (("current_z", "1"), ("lag_z", "1"))
_MAX_MEL_ROWS = 16


def _fingerprint(obj):
    return sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Handoff:
    """Immutable receipt of *proposed* provenance, not a dispatch credential."""
    operation: str
    source_sha256: str
    series_identity: str
    fold: str
    cohort_sha256: str
    plan_sha256: str
    plan: object
    origin_target_keys: tuple[tuple[int, int], ...]
    execution_authorized: bool = False
    conversion_kind: str = "none"
    max_quantization_error: float = 0.0


def _source(raw, *, site_id, units, clock, provenance):
    return d.qualify(raw, site_id=site_id, units=units,
                     clock=clock, provenance=provenance)


def _scientific_batch(series, *, operation, fold, horizon_ms, lag_ms):
    profile = d.CandidateContract(operation, series.units,
                                  sampling="irregular_accepted",
                                  missing="explicit_missing_accepted")
    split = d.split_chronological(series)
    scaler = d.fit_train_scaler(series, split)
    batch = d.prepare_forecasts(
        series, split, scaler, profile,
        fold=fold, horizon_ms=horizon_ms, lag_ms=lag_ms)
    if not 1 <= len(batch.examples) <= _MAX_MEL_ROWS:
        raise ValueError("MEL batch must be nonempty and within worker bounds")
    if any(not all(isfinite(z) and abs(z) <= 100.0 for z in row.feature_values)
           for row in batch.examples):
        raise ValueError("standardized features outside reviewed domain")
    cohort = tuple((row.origin_ms, row.target_ms) for row in batch.examples)
    proof = _fingerprint({
        "schema": "orc.handoff.batch.v1",
        "source": series.identity, "fold": fold, "operation": operation,
        "horizon": horizon_ms, "lag": lag_ms, "scale": scaler.training_rows_sha256,
        "origins": cohort, "features": [x.feature_values for x in batch.examples],
    })
    return batch, cohort, proof


def compile_mel(
    raw: bytes, *, site_id: str, units: d.Units, clock: d.Clock,
    provenance: d.Provenance, scope: a.Scope, operation: str,
    fold: str, horizon_ms: int, lag_ms: int,
    function: n.NativeObject | None = None, approval: m.Approval | None = None,
    budget: g.Budget | None = None,
    max_binary32_error: float | None = None,
) -> Handoff:
    """Compile source-verified features into existing MEL Seed + VFA/KAN graph.

    The returned graph must be executed by the *existing* a.Admission +
    g.execute or verified_graph.execute_verified with separately host-issued
    exact node grants. The checkpoint cannot be selected from model content.
    """
    if type(scope) is not a.Scope:
        raise ValueError("trusted existing MEL scope required")
    if operation not in ("vfa.evaluate", "kan.evaluate"):
        raise ValueError("unreviewed MEL scientific handoff")
    if type(budget) is not g.Budget:
        raise ValueError("explicit reviewed MEL budget required")
    if operation == "vfa.evaluate":
        if max_binary32_error is not None:
            raise ValueError("VFA binary32 conversion is unreviewed")
        if type(function) is not n.NativeObject or approval is not None:
            raise ValueError("reviewed VFA function required; checkpoint forbidden")
        body = function.message().body
        if body.WhichOneof("representation") != "function":
            raise ValueError("VFA function representation required")
        if tuple((x.name, x.unit) for x in body.axes) != _FEATURE_AXES:
            raise ValueError("VFA axes must be standardized dimensionless features")
    else:
        if max_binary32_error is not None and (
            type(max_binary32_error) is not float or
            not 0.0 <= max_binary32_error <= 1e-4
        ):
            raise ValueError("invalid explicit binary32 rounding budget")
        if function is not None or type(approval) is not m.Approval:
            raise ValueError("trusted reviewed KAN checkpoint required")
        ck = approval.checkpoint.message()
        if ck.layers[0].inputs != 2 or ck.layers[-1].outputs != 1:
            raise ValueError("KAN checkpoint requires two inputs and one output")
        first = ck.layers[0]
        bounds = [(float(first.grid[i * first.knots]),
                   float(first.grid[(i + 1) * first.knots - 1]))
                  for i in range(2)]
        if any(not (isfinite(lo) and isfinite(hi) and -100.0 <= lo < hi <= 100.0)
               for lo, hi in bounds):
            raise ValueError("unreviewed KAN input domain")
        # Only a canonical point seed is needed; this zero function is never
        # evaluated or treated as a trained forecasting model.
        function = n.gaussian([], [], [], constant=0.,
                              axes=_FEATURE_AXES, domain=bounds,
                              output_unit="1")
    series = _source(raw, site_id=site_id, units=units, clock=clock,
                     provenance=provenance)
    batch, cohort, batch_sha = _scientific_batch(
        series, operation=operation, fold=fold,
        horizon_ms=horizon_ms, lag_ms=lag_ms)
    coords = [list(item.feature_values) for item in batch.examples]
    conversion_error = 0.0
    if operation == "kan.evaluate":
        # The existing MEL transfer rejects lossy binary64->binary32 values.
        # Only an explicit host-approved numeric tolerance permits this
        # conversion; the exact measured loss is recorded and plan-bound.
        from struct import pack, unpack
        converted = []
        for row in coords:
            new_row = []
            for value in row:
                try:
                    binary32 = unpack("<f", pack("<f", value))[0]
                except (OverflowError, ValueError):
                    raise ValueError("KAN binary32 conversion overflow") from None
                if not isfinite(binary32):
                    raise ValueError("KAN binary32 conversion nonfinite")
                error = abs(value - binary32)
                if error and (max_binary32_error is None or error > max_binary32_error):
                    raise ValueError("unapproved or excessive binary32 conversion loss")
                conversion_error = max(conversion_error, error)
                new_row.append(binary32)
            converted.append(new_row)
        coords = converted
    points = n.points(function, coords)  # Original typed MEL binary64 object.
    node = (g.Vfa("evaluate", "seed", function)
            if operation == "vfa.evaluate" else
            g.Kan("evaluate", "seed", approval,
                  ("current_z", "lag_z"), ("score",)))
    # MEL's plan identity includes this ID and actual source-derived seed bytes.
    # The digest binds entire scientific provenance/cohort and host scope.
    anchor = _fingerprint({
        "schema": "orc.mel.handoff.v1",
        "source": series.identity, "cohort": batch_sha,
        "operation": operation, "scope": tuple(
            (scope.session, scope.workspace, scope.subject, scope.turn)),
        "checkpoint": approval.checkpoint.identity if approval else None,
        "function": function.identity,
        "rounding_budget": max_binary32_error,
        "observed_rounding_error": conversion_error,
    })
    plan = g.Plan("orc" + anchor[:32], scope, (g.Seed("seed", points), node), budget)
    return Handoff(operation, provenance.raw_sha256, series.identity, fold,
                   batch_sha, plan.identity, plan, cohort,
                   conversion_kind=("binary32_explicit" if operation == "kan.evaluate" and
                                    max_binary32_error is not None else "none"),
                   max_quantization_error=conversion_error)


def check_source_current(
    handoff: Handoff, raw: bytes, *,
    site_id: str, units: d.Units, clock: d.Clock,
    provenance: d.Provenance, source_current,
) -> bool:
    """Host-side source/plan preflight; it does not replace worker admission.

    The trusted host must repeat this on publication and drive existing
    Cancellation/Admission revocation if a source becomes stale in flight.
    No new daemon or orchestrator is created. Never pass this function itself
    as a substitute for a host-issued computation grant.
    """
    if type(handoff) is not Handoff or not callable(source_current):
        raise ValueError("trusted source handoff and freshness callback required")
    series = _source(raw, site_id=site_id, units=units,
                     clock=clock, provenance=provenance)
    if (series.identity != handoff.series_identity or
        provenance.raw_sha256 != handoff.source_sha256):
        raise ValueError("stale or substituted scientific source")
    plan = handoff.plan
    if type(plan) is g.Plan:
        actual = plan.identity
        if handoff.operation not in ("vfa.evaluate", "kan.evaluate"):
            raise ValueError("MEL handoff operation mismatch")
        if (len(plan.nodes) != 2 or type(plan.nodes[0]) is not g.Seed or
            plan.nodes[1].parent != "seed" or
            type(plan.nodes[1]) is not (
                g.Vfa if handoff.operation == "vfa.evaluate" else g.Kan)):
            raise ValueError("unexpected scientific graph")
    elif type(plan) is CpuPlan:
        actual = plan_digest(plan)
        if (handoff.operation != "temporal.kalman" or
            len(plan.steps) != 1 or
            plan.steps[0].operation != "temporal.kalman" or
            plan.steps[0].source.revision != series.identity[:40]):
            raise ValueError("unexpected deterministic graph")
    else:
        raise ValueError("unreviewed handoff plan")
    if (handoff.conversion_kind not in ("none", "binary32_explicit") or
        type(handoff.max_quantization_error) is not float or
        handoff.max_quantization_error < 0 or
        handoff.max_quantization_error > 1e-4 or
        (handoff.conversion_kind == "none" and
         handoff.max_quantization_error != 0.0) or
        (handoff.conversion_kind == "binary32_explicit" and
         handoff.operation != "kan.evaluate")):
        raise ValueError("unreviewed handoff precision declaration")
    if actual != handoff.plan_sha256 or handoff.execution_authorized is not False:
        raise ValueError("tampered handoff identity or authority")
    if source_current(handoff, series) is not True:
        raise ValueError("scientific source no longer current")
    return True


def compile_kalman(
    raw: bytes, *, site_id: str, units: d.Units, clock: d.Clock,
    provenance: d.Provenance, workspace_id: str, subject_id: str,
    build_sha: str, horizon_ms: int, model: TemporalModel,
    timeout_ms: int = 30000,
) -> Handoff:
    """Compile train-visible original observations to reviewed C17 CPU Kalman.

    Forecast is at the train-end snapshot, never a retrospective simulated
    observation with unavailable future data. Missings are masked explicitly.
    """
    if type(model) is not TemporalModel or type(horizon_ms) is not int or (
        not 1 <= horizon_ms <= 86_400_000
    ):
        raise ValueError("reviewed Kalman model and horizon required")
    series = _source(raw, site_id=site_id, units=units, clock=clock,
                     provenance=provenance)
    profile = d.CandidateContract("temporal.kalman", series.units)
    if not d.check_compatibility(series, profile).compatible:
        raise ValueError("Kalman scientific input incompatible")
    split = d.split_chronological(series)
    subset = series.rows[:split.train_stop]
    if len(subset) > 256 or len(subset) < 3:
        raise ValueError("bounded Kalman input requires 3..256 train rows")
    start = subset[0].timestamp_ms
    if any(row.timestamp_ms - start > 30 * 86_400_000 for row in subset):
        raise ValueError("Kalman worker time base limit")
    observed = tuple(
        TemporalSample(
            row.timestamp_ms - start,
            (row.value if row.observed and row.available_ms <= split.train_until_ms
             else None,),
            "source", row.observation_id)
        for row in subset)
    sequence = TemporalSequence(
        (_UNIT_TOKEN[series.units.symbol],), observed,
        "source", "imported", "unverified")
    validate(sequence, model)
    last = observed[-1].time_ms
    if horizon_ms > model.max_forecast_ms:
        raise ValueError("model forecast horizon unsupported")
    q = temporal.FilterRequest(
        schema_version=1, units=sequence.units, origin_id=sequence.origin_id,
        provenance_kind=sequence.provenance_kind, quality_declared="unverified",
        kind=model.kind, process_variance_per_second=model.process_variance_per_second,
        measurement_variance=model.measurement_variance,
        prior_variance=model.prior_variance,
        innovation_gate_sigma=model.innovation_gate_sigma,
        max_forecast_ms=model.max_forecast_ms,
        forecast_time_ms=last + horizon_ms)
    for item in observed:
        present = item.values[0] is not None
        q.samples.add(
            time_ms=item.time_ms, values=[item.values[0] if present else 0.0],
            observed=[present], source_id=item.source_id,
            observation_id=item.observation_id)
    frame = wire(q)
    route = ROUTES["temporal.kalman"]
    # No arbitrary plan nodes; COG-06 independently replays the Kalman output.
    stamp = SourceStamp(site_id, series.identity[:40], sha256(frame).hexdigest())
    anchor = _fingerprint({
        "schema": "orc.kalman.handoff.v1",
        "source": series.identity, "build": build_sha,
        "snapshot": split.train_until_ms, "horizon": horizon_ms,
        "model": (model.kind, model.process_variance_per_second,
                  model.measurement_variance, model.prior_variance,
                  model.innovation_gate_sigma, model.max_forecast_ms),
    })
    step = Step("kalman", "temporal.kalman", type_url(route.input_class),
                route.identity, frame, stamp, timeout_ms=min(timeout_ms, 10000))
    plan = CpuPlan("orc" + anchor[:32], workspace_id, subject_id,
                   build_sha, timeout_ms, (step,))
    return Handoff("temporal.kalman", provenance.raw_sha256, series.identity,
                   "train", _fingerprint(tuple(
                       (s.timestamp_ms, s.available_ms, s.observed) for s in subset)),
                   plan_digest(plan), plan, tuple())


def execute_bound_mel(
    host: a.Admission, handoff: Handoff, grants: tuple,
    tolerances: tuple, *, raw: bytes, site_id: str, units: d.Units,
    clock: d.Clock, provenance: d.Provenance, source_current,
    cancellation: g.Cancellation | None = None,
) -> vg.Guarded:
    """Trusted host publication gate around the SAME verified MEL executor.

    Preflight and *postflight* independently recheck original scientific
    source identity and host-supplied freshness. A stale/replaced source must
    never make a verified worker payload visible to callers. All actual
    admission, resource limits, cancellation and computation are delegated
    unchanged to MEL. This wrapper neither watches sources asynchronously
    nor interrupts a worker; host can use original Cancellation/revoke.
    """
    if type(host) is not a.Admission or type(handoff) is not Handoff or (
        type(handoff.plan) is not g.Plan
    ):
        raise ValueError("original authorized MEL host and graph required")
    arguments = dict(site_id=site_id,units=units,clock=clock,
                     provenance=provenance,source_current=source_current)
    try:
        check_source_current(handoff, raw, **arguments)
    except Exception:
        return vg.Guarded("stale_source")
    result = vg.execute_verified(host, handoff.plan, grants, tolerances,
                                 cancellation=cancellation)
    if result.status != "verified":
        return result  # MEL already suppresses failed/revoked/cancelled data.
    try:
        check_source_current(handoff, raw, **arguments)
    except Exception:
        # Worker grants and consumed work stay charged, but nothing publishes.
        return vg.Guarded("stale_source", None, None, result.charged_work,
                          result.reserved_bytes, result.reserved_calls)
    return result
