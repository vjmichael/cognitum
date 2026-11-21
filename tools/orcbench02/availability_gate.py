"""BENCH-02-R1: fail-closed offline validation of external AWC METAR snapshots.

A provider receipt clock is NOT an independently attested public-availability
clock. These candidate records may not authorize operational forecasting.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from urllib.parse import parse_qs, urlsplit

class SourceRefusal(ValueError):
    """Unqualified original-source candidate."""

def require(ok, reason):
    if not ok:
        raise SourceRefusal(reason)

@dataclass(frozen=True)
class CapturedSnapshot:
    url: str
    station: str
    fetched_complete_ms: int
    sha256_hex: str
    capture_evidence: str  # declared reference, NOT independent authentication

@dataclass(frozen=True)
class Observation:
    station: str
    observed_ms: int
    awc_receipt_ms: int
    first_snapshot_seen_ms: int
    temperature_k: float | None
    raw_report: str

@dataclass(frozen=True)
class CandidateDataset:
    source_sha256: str
    station: str
    observations: tuple[Observation, ...]
    missing_temperature_count: int
    source_url: str
    capture_evidence: str
    receipt_status: str = "AWC_REPORTED_NOT_PUBLICATION_ATTESTED"
    asof_status: str = "NOT_QUALIFIED_UNTIL_INDEPENDENT_CAPTURE_ATTESTATION"
    admissible_for_production: bool = False

    def audit(self):
        return {
            "source_sha256": self.source_sha256, "station": self.station,
            "observations": len(self.observations),
            "missing_temperature_count": self.missing_temperature_count,
            "source_url": self.source_url, "capture_evidence": self.capture_evidence,
            "receipt_status": self.receipt_status, "asof_status": self.asof_status,
            "admissible_for_production": self.admissible_for_production,
        }

def receipt_ms(value):
    require(type(value) is str and value.strip(), "missing AWC receipt clock")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceRefusal("invalid AWC receipt clock") from exc
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None,
            "AWC receipt clock must contain a timezone")
    return int(parsed.astimezone(timezone.utc).timestamp() * 1000)

def inspect_awc_metar(raw: bytes, witness: CapturedSnapshot) -> CandidateDataset:
    """No networking, trusted transport, historical public availability or grants."""
    require(type(raw) is bytes and 2 <= len(raw) <= 20_000_000,
            "empty/oversized raw source")
    require(type(witness) is CapturedSnapshot, "missing source witness")
    station = witness.station
    require(type(station) is str and len(station) == 4 and
            station.isascii() and station.isalpha() and station.isupper(),
            "station must be an uppercase ICAO identifier")
    require(type(witness.fetched_complete_ms) is int and
            witness.fetched_complete_ms > 0, "capture clock unavailable")
    require(type(witness.capture_evidence) is str and
            len(witness.capture_evidence.strip()) >= 12,
            "missing external capture-evidence reference")
    sha = sha256(raw).hexdigest()
    require(witness.sha256_hex == sha, "capture source SHA mismatch")
    try:
        u = urlsplit(witness.url)
        qs = parse_qs(u.query, strict_parsing=True)
        valid_url = (u.scheme == "https" and u.hostname == "aviationweather.gov"
            and u.port is None and u.username is None and u.password is None
            and u.path == "/api/data/metar" and not u.fragment
            and qs.get("ids") == [station] and qs.get("format") == ["json"]
            and set(qs) <= {"ids", "format", "hours", "date"})
    except ValueError:
        valid_url = False
    require(valid_url, "unqualified endpoint/HTTPS/station/query")
    try:
        items = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise SourceRefusal("invalid source UTF-8 JSON") from exc
    require(type(items) is list and 0 < len(items) <= 10000,
            "expected bounded nonempty METAR report list")
    observations = []
    seen = set()
    for i, row in enumerate(items):
        require(type(row) is dict and row.get("icaoId") == station,
                f"row {i}: wrong station")
        second = row.get("obsTime")
        require(type(second) is int and 946684800 <= second <= 4102444800,
                f"row {i}: missing/invalid observation epoch")
        observed = second * 1000
        received = receipt_ms(row.get("receiptTime"))
        require(observed <= received <= witness.fetched_complete_ms,
                f"row {i}: impossible observation/receipt/capture clock")
        require(observed not in seen,
                f"row {i}: duplicate/revision requires explicit first-seen freeze")
        seen.add(observed)
        raw_report = row.get("rawOb")
        require(type(raw_report) is str and raw_report.strip() and
                station in raw_report.split(),
                f"row {i}: missing/wrong raw report")
        val = row.get("temp")
        require(val is None or (type(val) in (int, float) and math.isfinite(val)),
                f"row {i}: nonfinite/unqualified Celsius")
        kelvin = None if val is None else float(val) + 273.15
        require(kelvin is None or kelvin > 0, f"row {i}: invalid Kelvin")
        observations.append(Observation(station, observed, received,
                                        witness.fetched_complete_ms,
                                        kelvin, raw_report))
    require(all(a.observed_ms < b.observed_ms
                for a, b in zip(observations, observations[1:])),
            "out-of-order observations")
    return CandidateDataset(sha, station, tuple(observations),
                            sum(o.temperature_k is None for o in observations),
                            witness.url, witness.capture_evidence)

def provisional_asof(dataset: CandidateDataset, origin_ms: int):
    """Research-only earliest candidate view; NOT historical public access proof."""
    require(type(dataset) is CandidateDataset and not dataset.admissible_for_production,
            "only unpromoted source candidates allowed")
    require(type(origin_ms) is int, "origin must be integer UTC milliseconds")
    return tuple(o for o in dataset.observations
                 if o.observed_ms <= origin_ms
                 and o.awc_receipt_ms <= origin_ms
                 and o.first_snapshot_seen_ms <= origin_ms
                 and o.temperature_k is not None)
