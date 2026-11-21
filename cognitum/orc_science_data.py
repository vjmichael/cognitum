"""ORCH-01B: bounded, immutable, backend-neutral scientific-data contracts.

A host supplies bytes and a claimed provenance record. The code verifies
content-byte custody, but NOT upstream publisher identity, original sensors,
licensing, or empirical suitability. Nothing here executes a model or grants
access to tools; ORCH-01A's trusted cooperative executor remains unchanged.

No data is imputed, interpolated, silently unit-converted, or fit using
calibration/test observations. Explicit publication/availability times stop
retroactively available values from being used as forecast-time features.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
from hashlib import sha256
from io import StringIO
from math import fsum, isfinite, sqrt
from types import MappingProxyType
import json
import re

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 50_000
MAX_MAGNITUDE = 1e12
_MAX_MS = 253402300799999
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,95}\Z", re.ASCII)
_UNITS = MappingProxyType({
    "discharge": ("m3/s",),
    "water_level": ("m",),
    "temperature": ("K",),
    "dimensionless": ("1",),
})
_HEADER = ("timestamp_ms", "available_ms", "value", "observed", "observation_id")
_FOLDS = ("train", "cal", "test")


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")).hexdigest()


def _identifier(value):
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError("invalid scientific identity")
    return value


def _ms(value):
    if type(value) is not int or not 0 <= value <= _MAX_MS:
        raise ValueError("invalid UTC epoch milliseconds")
    return value


@dataclass(frozen=True, slots=True)
class Units:
    quantity: str
    symbol: str

    def __post_init__(self):
        if type(self.quantity) is not str or type(self.symbol) is not str or (
            self.symbol not in _UNITS.get(self.quantity, ())
        ):
            raise ValueError("unknown or incompatible scientific units")


@dataclass(frozen=True, slots=True)
class Clock:
    representation: str = "unix_ms_utc"
    nominal_interval_ms: int | None = None

    def __post_init__(self):
        if self.representation != "unix_ms_utc":
            raise ValueError("unreviewed time base or timezone")
        if self.nominal_interval_ms is not None and (
            type(self.nominal_interval_ms) is not int or
            not 1 <= self.nominal_interval_ms <= 366 * 86_400_000
        ):
            raise ValueError("invalid nominal sampling interval")


@dataclass(frozen=True, slots=True)
class Provenance:
    publisher: str
    source_reference: str
    raw_sha256: str
    rights_status: str = "unknown"
    unit_evidence: str = "declared"

    def __post_init__(self):
        _identifier(self.publisher)
        if type(self.source_reference) is not str or not 1 <= len(self.source_reference) <= 512:
            raise ValueError("source reference required")
        if type(self.raw_sha256) is not str or not _SHA.fullmatch(self.raw_sha256):
            raise ValueError("source SHA256 required")
        if self.rights_status not in ("unknown", "publisher_reported"):
            raise ValueError("unverified licensing cannot be certified here")
        if self.unit_evidence not in ("declared", "publisher_documented"):
            raise ValueError("sensor-level units cannot be certified here")


@dataclass(frozen=True, slots=True)
class Observation:
    timestamp_ms: int
    available_ms: int
    value: float | None
    observed: bool
    observation_id: str

    def __post_init__(self):
        _ms(self.timestamp_ms)
        _ms(self.available_ms)
        if self.available_ms < self.timestamp_ms:
            raise ValueError("observation availability precedes observation time")
        _identifier(self.observation_id)
        if type(self.observed) is not bool:
            raise ValueError("explicit missingness boolean required")
        if self.observed:
            if type(self.value) is not float or not isfinite(self.value) or abs(self.value) > MAX_MAGNITUDE:
                raise ValueError("finite observed numeric value required")
        elif self.value is not None:
            raise ValueError("missing observations must have no value")


@dataclass(frozen=True, slots=True)
class QualifiedSeries:
    site_id: str
    units: Units
    clock: Clock
    provenance: Provenance
    rows: tuple[Observation, ...]
    identity: str

    @property
    def has_missing(self):
        return any(not row.observed for row in self.rows)


def qualify(raw: bytes, *, site_id: str, units: Units, clock: Clock,
            provenance: Provenance) -> QualifiedSeries:
    """Read exact custody-verified UTF-8 CSV bytes, never files or URLs."""
    _identifier(site_id)
    if type(units) is not Units or type(clock) is not Clock or type(provenance) is not Provenance:
        raise ValueError("typed units, clock and source provenance required")
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("scientific source byte bound")
    if sha256(raw).hexdigest() != provenance.raw_sha256:
        raise ValueError("source content SHA256 mismatch")
    try:
        decoded = raw.decode("utf-8")
        parsed = csv.reader(StringIO(decoded, newline=""), strict=True)
        if tuple(next(parsed)) != _HEADER:
            raise ValueError("unreviewed CSV field contract")
        records = []
        ids = set()
        previous = -1
        for cols in parsed:
            if len(cols) != len(_HEADER) or len(records) >= MAX_ROWS:
                raise ValueError("invalid or oversized observation row")
            time_s, available_s, value_s, observed_s, row_id = cols
            if observed_s not in ("0", "1"):
                raise ValueError("missingness must be explicit 0 or 1")
            if not re.fullmatch(r"(0|[1-9][0-9]*)", time_s) or not re.fullmatch(
                r"(0|[1-9][0-9]*)", available_s
            ):
                raise ValueError("noncanonical timestamp")
            observed = observed_s == "1"
            if observed and not value_s:
                raise ValueError("missing observed measurement")
            if not observed and value_s:
                raise ValueError("silent imputation or missing value substitution")
            value = float(value_s) if observed else None
            row = Observation(int(time_s), int(available_s), value, observed, row_id)
            if row.timestamp_ms <= previous or row_id in ids:
                raise ValueError("unordered, duplicated or conflicting observation")
            if clock.nominal_interval_ms is not None and previous >= 0 and (
                row.timestamp_ms - previous != clock.nominal_interval_ms
            ):
                raise ValueError("unmarked nominal sampling gap")
            previous = row.timestamp_ms
            ids.add(row_id)
            records.append(row)
    except (UnicodeError, csv.Error, StopIteration, OverflowError) as exc:
        raise ValueError("invalid scientific CSV source") from exc
    if len(records) < 15:
        raise ValueError("insufficient chronological observations")
    identity = _digest({
        "schema": "orc.science.source.v1", "site": site_id,
        "quantity": units.quantity, "unit": units.symbol,
        "clock": (clock.representation, clock.nominal_interval_ms),
        "publisher": provenance.publisher, "source": provenance.source_reference,
        "raw": provenance.raw_sha256, "unit_evidence": provenance.unit_evidence,
        "rights": provenance.rights_status,
    })
    return QualifiedSeries(site_id, units, clock, provenance, tuple(records), identity)


@dataclass(frozen=True, slots=True)
class ChronologicalSplit:
    series_identity: str
    train_stop: int
    cal_stop: int
    row_count: int
    train_until_ms: int

    def bounds(self, fold):
        if fold not in _FOLDS:
            raise ValueError("unreviewed train/cal/test fold")
        return {"train": (0, self.train_stop),
                "cal": (self.train_stop, self.cal_stop),
                "test": (self.cal_stop, self.row_count)}[fold]


def split_chronological(series: QualifiedSeries) -> ChronologicalSplit:
    if type(series) is not QualifiedSeries:
        raise ValueError("qualified source required")
    count = len(series.rows)
    a, b = (3 * count) // 5, (4 * count) // 5
    if a < 6 or b <= a or b >= count:
        raise ValueError("insufficient chronological folds")
    return ChronologicalSplit(series.identity, a, b, count, series.rows[a - 1].timestamp_ms)


def _check_split(series, split):
    if (type(series) is not QualifiedSeries or type(split) is not ChronologicalSplit or
        split.series_identity != series.identity or split.row_count != len(series.rows) or
        split.train_until_ms != series.rows[split.train_stop - 1].timestamp_ms or
        not 6 <= split.train_stop < split.cal_stop < split.row_count or
        split.train_stop != (3 * split.row_count) // 5 or
        split.cal_stop != (4 * split.row_count) // 5):
        raise ValueError("stale or incompatible chronological split")


@dataclass(frozen=True, slots=True)
class TrainScaler:
    series_identity: str
    training_rows_sha256: str
    cutoff_ms: int
    units: Units
    count: int
    mean: float
    standard_deviation: float


def fit_train_scaler(series: QualifiedSeries, split: ChronologicalSplit) -> TrainScaler:
    """Only measurements available by train-end may fit the transformation."""
    _check_split(series, split)
    visible = tuple(row for row in series.rows[:split.train_stop]
                    if row.observed and row.available_ms <= split.train_until_ms)
    if len(visible) < 3:
        raise ValueError("insufficient train-visible observations")
    mean = fsum(row.value for row in visible) / len(visible)
    variance = fsum((row.value - mean) ** 2 for row in visible) / len(visible)
    if not isfinite(variance) or variance <= 0:
        raise ValueError("constant or nonfinite train scale")
    training_hash = _digest(tuple((row.observation_id, row.timestamp_ms,
                                   row.available_ms, row.value) for row in visible))
    return TrainScaler(series.identity, training_hash, split.train_until_ms,
                       series.units, len(visible), mean, sqrt(variance))


@dataclass(frozen=True, slots=True)
class CandidateContract:
    """Host-reviewed input *requirements*, never model- or user-issued grant."""
    operation: str
    units: Units
    time_base: str = "unix_ms_utc"
    sampling: str = "irregular_accepted"
    missing: str = "explicit_missing_accepted"
    minimum_unit_evidence: str = "declared"

    def __post_init__(self):
        from .orc_graph import catalog
        # MEL's reviewed descriptors are input-compatibility candidates,
        # never permission. The trusted host separately installs/adopts routes.
        from .mel.admission import routes as mel_routes
        candidates = {x.operation for x in catalog()}
        candidates.update(x.operation for x in mel_routes(include_engines=True))
        if self.operation not in candidates:
            raise ValueError("unknown mathematical capability")
        if type(self.units) is not Units or self.time_base != "unix_ms_utc":
            raise ValueError("typed units and UTC time required")
        if self.sampling not in ("irregular_accepted", "regular_required"):
            raise ValueError("unreviewed sampling acceptance")
        if self.missing not in ("explicit_missing_accepted", "complete_required"):
            raise ValueError("unreviewed missingness acceptance")
        if self.minimum_unit_evidence not in ("declared", "publisher_documented"):
            raise ValueError("unverified unit evidence")


@dataclass(frozen=True, slots=True)
class Compatibility:
    compatible: bool
    reasons: tuple[str, ...]
    execution_authorized: bool = False


def check_compatibility(series: QualifiedSeries, contract: CandidateContract) -> Compatibility:
    if type(series) is not QualifiedSeries or type(contract) is not CandidateContract:
        raise ValueError("typed scientific input contract required")
    reasons = []
    if series.units != contract.units:
        reasons.append("quantity_or_unit_mismatch_no_auto_conversion")
    if series.clock.representation != contract.time_base:
        reasons.append("time_base_mismatch")
    if contract.sampling == "regular_required" and series.clock.nominal_interval_ms is None:
        reasons.append("irregular_clock_unsupported")
    if contract.missing == "complete_required" and series.has_missing:
        reasons.append("missing_measurements_unsupported")
    if (contract.minimum_unit_evidence == "publisher_documented" and
        series.provenance.unit_evidence != "publisher_documented"):
        reasons.append("insufficient_reported_unit_evidence")
    return Compatibility(not reasons, tuple(reasons))


@dataclass(frozen=True, slots=True)
class ForecastExample:
    origin_ms: int
    target_ms: int
    feature_values: tuple[float, float]
    target: float


@dataclass(frozen=True, slots=True)
class PreparedBatch:
    source_identity: str
    operation: str
    fold: str
    horizon_ms: int
    lag_ms: int
    eligible_origins: int
    skipped: tuple[tuple[str, int], ...]
    examples: tuple[ForecastExample, ...]
    execution_authorized: bool = False


def prepare_forecasts(series: QualifiedSeries, split: ChronologicalSplit,
                      scaler: TrainScaler, contract: CandidateContract, *,
                      fold: str, horizon_ms: int, lag_ms: int) -> PreparedBatch:
    """Historical as-of forecast cohort; never passes future target as a feature.

    The previous observation and lag must both have been published by the
    forecast origin, and forecast target must remain in the selected fold.
    Models/selection code must keep cal/test labels out of training.
    """
    _check_split(series, split)
    compatibility = check_compatibility(series, contract)
    if not compatibility.compatible:
        raise ValueError("capability input incompatible: " + ",".join(compatibility.reasons))
    if (type(scaler) is not TrainScaler or scaler.series_identity != series.identity or
        scaler.cutoff_ms != split.train_until_ms or scaler.units != series.units or
        scaler.standard_deviation <= 0):
        raise ValueError("incompatible train-only transformation")
    expected = fit_train_scaler(series, split)
    if scaler != expected:
        raise ValueError("transformation must match independently refitted train-only data")
    if fold not in _FOLDS:
        raise ValueError("unknown chronological fold")
    if any(type(x) is not int or not 1 <= x <= 366 * 86_400_000
           for x in (horizon_ms, lag_ms)):
        raise ValueError("positive exact-time horizon and lag required")
    left, right = split.bounds(fold)
    observations = series.rows
    at_time = {row.timestamp_ms: (i, row) for i, row in enumerate(observations)}
    skip = {"origin_unavailable": 0, "lag_unavailable": 0,
            "target_missing_or_outside_fold": 0}
    selected = []
    for origin in observations[left:right]:
        if not origin.observed or origin.available_ms > origin.timestamp_ms:
            skip["origin_unavailable"] += 1
            continue
        prev = at_time.get(origin.timestamp_ms - lag_ms)
        if (prev is None or not prev[1].observed or
                prev[1].available_ms > origin.timestamp_ms):
            skip["lag_unavailable"] += 1
            continue
        future = at_time.get(origin.timestamp_ms + horizon_ms)
        if (future is None or not left <= future[0] < right or not future[1].observed):
            skip["target_missing_or_outside_fold"] += 1
            continue
        selected.append(ForecastExample(
            origin.timestamp_ms, future[1].timestamp_ms,
            ((origin.value - scaler.mean) / scaler.standard_deviation,
             (prev[1].value - scaler.mean) / scaler.standard_deviation),
            future[1].value))
    return PreparedBatch(series.identity, contract.operation, fold,
                         horizon_ms, lag_ms, right - left,
                         tuple(sorted(skip.items())), tuple(selected))


def assert_matched_cohorts(*batches: PreparedBatch) -> tuple[tuple[int, int], ...]:
    """Never silently intersect cohorts to make an algorithm look stronger."""
    if len(batches) < 2 or any(type(batch) is not PreparedBatch for batch in batches):
        raise ValueError("at least two typed candidate batches required")
    initial = batches[0]
    keys = tuple((row.origin_ms, row.target_ms) for row in initial.examples)
    for item in batches[1:]:
        if (item.source_identity != initial.source_identity or item.fold != initial.fold or
            item.horizon_ms != initial.horizon_ms or item.lag_ms != initial.lag_ms or
            item.eligible_origins != initial.eligible_origins or
            tuple((row.origin_ms, row.target_ms) for row in item.examples) != keys):
            raise ValueError("candidate cohorts differ: matched evaluation refused")
    return keys
