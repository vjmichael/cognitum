"""BENCH-02-R1 source-gate synthetic negatives. No external data/scores."""
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import pytest
from tools.orcbench02.availability_gate import (
    CapturedSnapshot, SourceRefusal, inspect_awc_metar, provisional_asof)

BASE = 1_700_000_000
FETCHED = (BASE + 500) * 1000

def fixture(rows=None):
    if rows is None:
        rows = [
            {"icaoId":"KPHX", "obsTime":BASE, "receiptTime":"2023-11-14T22:15:00Z",
             "temp":21.3, "rawOb":"KPHX 142213Z 18006KT 10SM CLR 21/03 A3000"},
            {"icaoId":"KPHX", "obsTime":BASE+100, "receiptTime":"2023-11-14T22:16:00Z",
             "temp":None, "rawOb":"KPHX 142216Z AUTO 18006KT 10SM CLR"},
        ]
    raw = json.dumps(rows, sort_keys=True, separators=(",",":")).encode()
    return raw, CapturedSnapshot(
        "https://aviationweather.gov/api/data/metar?ids=KPHX&format=json&hours=6",
        "KPHX", FETCHED, sha256(raw).hexdigest(),
        "external-journal-not-authenticated")

def test_source_unit_clock_missing_and_nonpromotion():
    raw, witness = fixture()
    data = inspect_awc_metar(raw, witness)
    assert data.source_sha256 == sha256(raw).hexdigest()
    assert data.observations[0].temperature_k == pytest.approx(294.45)
    assert data.missing_temperature_count == 1
    assert not data.admissible_for_production
    assert "NOT_QUALIFIED" in data.asof_status
    assert "NOT_PUBLICATION_ATTESTED" in data.receipt_status
    assert data.audit()["observations"] == 2
    assert provisional_asof(data, (BASE + 200)*1000) == ()
    assert len(provisional_asof(data, FETCHED)) == 1

def test_tampered_snapshot_rejected():
    raw, witness = fixture()
    with pytest.raises(SourceRefusal, match="SHA mismatch"):
        inspect_awc_metar(raw + b" ", witness)

@pytest.mark.parametrize("url", [
    "http://aviationweather.gov/api/data/metar?ids=KPHX&format=json",
    "https://evil.example/api/data/metar?ids=KPHX&format=json",
    "https://aviationweather.gov.evil.example/api/data/metar?ids=KPHX&format=json",
    "https://aviationweather.gov/api/data/metar?ids=KLAX&format=json",
    "https://aviationweather.gov/api/data/metar?ids=KPHX&format=xml",
    "https://aviationweather.gov/api/data/metar?ids=KPHX&format=json&x=1",
])
def test_no_wrong_server_query_or_identity(url):
    raw, witness = fixture()
    with pytest.raises(SourceRefusal, match="endpoint"):
        inspect_awc_metar(raw, replace(witness,url=url))

@pytest.mark.parametrize("change", [
    {"icaoId":"KLAX"},
    {"obsTime":"2023-11-14T22:13:20Z"},
    {"receiptTime":None},
    {"receiptTime":"2023-11-14 22:15:00"},
    {"receiptTime":"2000-01-01T00:00:00Z"},
    {"temp":"21.3"},
    {"temp":float("inf")},
    {"rawOb":"KLAX corrupt"},
])
def test_unqualified_row_rejected(change):
    raw,_ = fixture()
    rows=json.loads(raw)
    rows[0].update(change)
    raw,witness=fixture(rows)
    with pytest.raises(SourceRefusal):
        inspect_awc_metar(raw,witness)

def test_revised_duplicate_refused_not_silently_chosen():
    raw,_=fixture()
    rows=json.loads(raw)
    rows[1]["obsTime"]=rows[0]["obsTime"]
    raw,witness=fixture(rows)
    with pytest.raises(SourceRefusal,match="duplicate"):
        inspect_awc_metar(raw,witness)

def test_reordered_sample_refused():
    raw,_=fixture()
    raw,witness=fixture(json.loads(raw)[::-1])
    with pytest.raises(SourceRefusal,match="out-of-order"):
        inspect_awc_metar(raw,witness)

def test_capture_before_receipt_refused():
    raw,witness=fixture()
    with pytest.raises(SourceRefusal,match="clock"):
        inspect_awc_metar(raw,replace(witness,fetched_complete_ms=BASE*1000))

def test_missing_capture_reference_refused():
    raw,witness=fixture()
    with pytest.raises(SourceRefusal,match="capture-evidence"):
        inspect_awc_metar(raw,replace(witness,capture_evidence=""))

def test_invalid_asof_origin_refused():
    raw,witness=fixture()
    data=inspect_awc_metar(raw,witness)
    with pytest.raises(SourceRefusal,match="milliseconds"):
        provisional_asof(data,"not-a-time")
