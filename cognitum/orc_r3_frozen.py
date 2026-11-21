"""Explicit research-only original R3 cohort identity for Orc's native paths.

This opt-in contract is not a provider signature, an MEL admission, or any
authority to recover retroactive first-availability.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import re

_SHA = re.compile(r"[0-9a-f]{64}\Z")
PROTOCOL_SHA = "fd0b6a372ee5cd9ee8870ad20c475261460a069daf4fd52f56e8dcc2961a5104"
HOUR = 3_600_000

@dataclass(frozen=True, slots=True)
class ResearchCohort:
    station: str
    original_noaa_sha256: str
    original_r3_cohort_sha256: str
    derived_csv_sha256: str
    horizon_ms: int
    fold_pairs: tuple[tuple[tuple[int, int], ...], ...]
    fold_pair_sha256: tuple[str, str, str]
    original_protocol_sha256: str = PROTOCOL_SHA
    train_stop: int = 115
    cal_stop: int = 153
    row_count: int = 192
    first_capture_test_eligible: int = 0
    execution_authorized: bool = False

    def __post_init__(self):
        if (self.station not in ("KSEA","KDEN","KATL") or
            self.horizon_ms not in (HOUR,3*HOUR,6*HOUR) or
            (self.train_stop,self.cal_stop,self.row_count)!=(115,153,192) or
            self.first_capture_test_eligible != 0 or
            self.original_protocol_sha256 != PROTOCOL_SHA or
            self.execution_authorized is not False or
            type(self.fold_pairs) is not tuple or len(self.fold_pairs)!=3 or
            type(self.fold_pair_sha256) is not tuple or len(self.fold_pair_sha256)!=3):
            raise ValueError("unregistered research-only R3 cohort")
        if any(type(x) is not str or _SHA.fullmatch(x) is None for x in (
            self.original_noaa_sha256,self.original_r3_cohort_sha256,
            self.derived_csv_sha256,*self.fold_pair_sha256)):
            raise ValueError("original science provenance SHA missing")
        for fold, pin in zip(self.fold_pairs,self.fold_pair_sha256):
            if type(fold) is not tuple or not fold:
                raise ValueError("empty R3 science fold")
            prev=-1
            for pair in fold:
                if (type(pair) is not tuple or len(pair)!=2 or
                    any(type(x) is not int for x in pair) or
                    pair[0] <= prev or pair[1]-pair[0] != self.horizon_ms or
                    pair[0]%HOUR != 0 or pair[1]%HOUR != 0):
                    raise ValueError("unaligned or reordered original R3 pair")
                prev=pair[0]
            canonical=json.dumps([list(p) for p in fold],separators=(",",":"),
                                 sort_keys=True).encode()
            if sha256(canonical).hexdigest()!=pin:
                raise ValueError("original R3 pair hash mismatch")

    @property
    def identity(self):
        material=(self.station,self.original_noaa_sha256,
            self.original_r3_cohort_sha256,self.derived_csv_sha256,
            self.original_protocol_sha256,self.horizon_ms,self.fold_pair_sha256)
        return sha256(json.dumps(material,sort_keys=True,separators=(",",":")).encode()).hexdigest()
