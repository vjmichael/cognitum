"""C08 admission policy: exact/FTS5 first, optional HDC only with evidence.

No model-supplied performance report may grant execution. A host-reviewed,
independent benchmark receipt is required to enable this experimental path.
HDC is never a substitute for canonical verification or authorization.
"""
from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RetrievalMeasurements:
    dataset_id: str
    trials: int
    exact_recall: float
    hdc_recall: float
    exact_median_ms: float
    hdc_median_ms: float
    verified_false_positives: int
    independent_host_measurement: bool

    def __post_init__(self):
        if not self.dataset_id or len(self.dataset_id) > 128 or self.trials < 30:
            raise ValueError("insufficient independent benchmark coverage")
        if not all(math.isfinite(v) for v in (
            self.exact_recall, self.hdc_recall, self.exact_median_ms,
            self.hdc_median_ms,
        )):
            raise ValueError("nonfinite measurements")
        if not 0 <= self.exact_recall <= 1 or not 0 <= self.hdc_recall <= 1:
            raise ValueError("invalid retrieval recall")
        if self.exact_median_ms <= 0 or self.hdc_median_ms <= 0:
            raise ValueError("invalid retrieval latency")
        if self.verified_false_positives < 0:
            raise ValueError("invalid false-positive count")


@dataclass(frozen=True)
class Admission:
    enabled: bool
    route: str
    reason: str


def choose_retrieval(
    *,
    user_opted_in: bool,
    host_approved: bool,
    independent_measurements: RetrievalMeasurements | None,
    min_speedup: float = 1.25,
) -> Admission:
    """Conservative route selector; no automatic HDC promotion from results.

    This is only an inert decision helper. Actual tool authorization, source
    scope and current canonical reads remain Lu host responsibilities.
    """
    if not user_opted_in:
        return Admission(False, "exact_or_fts5", "HDC_DISABLED_BY_DEFAULT")
    if not host_approved:
        return Admission(False, "exact_or_fts5", "HOST_HAS_NOT_APPROVED")
    if independent_measurements is None or not independent_measurements.independent_host_measurement:
        return Admission(False, "exact_or_fts5", "NO_INDEPENDENT_BENCHMARK")
    m = independent_measurements
    if m.verified_false_positives or m.hdc_recall < m.exact_recall:
        return Admission(False, "exact_or_fts5", "QUALITY_NOT_NONINFERIOR")
    if not math.isfinite(min_speedup) or min_speedup < 1.0:
        raise ValueError("invalid measured speedup threshold")
    if m.exact_median_ms / m.hdc_median_ms < min_speedup:
        return Admission(False, "exact_or_fts5", "NO_MEASURED_SPEED_ADVANTAGE")
    return Admission(True, "hdc_candidates_with_canonical_recheck", "MEASURED_OPTIONAL_BENEFIT")
