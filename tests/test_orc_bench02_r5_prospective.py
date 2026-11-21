"""R5 independent synthetic future-witness refusal and historic negative locks.

These tests are deliberately SYNTHETIC. They do not claim first real public
source availability. Real acceptance requires independently downloaded GitHub
artifact ZIPs and authenticated GitHub creation timestamps.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
import json
import pytest

from tools.orcbench02 import prospective_r5 as p

def metar(station,observed_ms,temp=17.,suffix="a"):
    obs=int(observed_ms//1000)
    return json.dumps([{
        "icaoId":station,"obsTime":obs,
        "receiptTime":datetime.fromtimestamp(obs+60,timezone.utc).isoformat(),
        "rawOb":f"{station} METAR_{obs}_{suffix} WND CALM",
        "temp":temp}],sort_keys=True,separators=(",",":")).encode()

def fake_capture(lane,seq,started_ms,raw,prior=None,artifact=None,run=None,anchor_ms=None):
    r=p.new_capture(raw,lane=lane,seq=seq,prev=prior or p.GENESIS,
        started=started_ms,ended=started_ms+1000)
    return dict(record=r,anchor=dict(id=artifact or 1000+seq,
        run_id=run or 9000+seq,created_ms=anchor_ms or started_ms+2000,
        archive_sha256=p.sha(b"synthetic-not-a-GitHub-artifact"),
        independently_downloaded_from_GitHub=True))

def source_profile():
    origin=p.epoch_ms("2026-11-26T12:00:00Z")
    events=[];hashes={lane:p.GENESIS for lane in p.LANES}
    # Mocked 10-minute source archive for 27 hours, including earliest 24h lag.
    base=origin-25*p.HOUR
    for seq in range(27*6+1):
        started=base+seq*600000+30000
        bucket_end=(started//p.HOUR)*p.HOUR
        observed=bucket_end-7*60000
        raw=metar("KBOS",observed)
        for lane in p.LANES:
            e=fake_capture(lane,seq,started+((lane=="B")*1000),raw,
                prior=hashes[lane],artifact=100000+(lane=="B")*10000+seq,
                run=200000+(lane=="B")*10000+seq)
            hashes[lane]=e["record"]["record_sha256"]
            events.append(e)
    return origin,events

def test_protocol_is_source_locked_before_any_new_collection():
    q=p.prereg()
    assert q["prospective_data"]["sites_fixed_order"]==["KBOS","KMSP","KPHX"]
    assert q["prospective_data"]["fold_hours"]=={"train":336,"calibration":168,"test":168}
    assert q["prospective_data"]["forecast_issue_offset_minutes_after_hour_end"]==20
    assert q["witnesses"]["unattested_global_publisher_first_available_claim"] is False
    assert q["execution"]["witness_production_activation_is_out_of_scope_for_R5_documentation_and_fixture_qualification"]
    assert q["prospective_data"]["collection_activation"].startswith("explicit")

def test_original_source_record_round_trip_does_not_grant_publisher_or_execution():
    origin=p.epoch_ms("2026-11-26T12:00:00Z")
    raw=metar("KBOS",origin-7*60000)
    rec=p.new_capture(raw,lane="A",seq=0,prev=p.GENESIS,
                      started=origin+60000,ended=origin+62000)
    rows=p.verify_capture(rec)
    assert len(rows)==1 and rows[0]["site"]=="KBOS"
    assert rows[0]["bucket_end_ms"]==origin
    assert not rec["global_publisher_first_available_proven"]
    assert not rec["execution_authorized"]
    assert rec["source_sha256"]==p.sha(raw)

def test_original_source_tamper_and_backdated_utc_clock_refused():
    origin=p.epoch_ms("2026-11-26T12:00:00Z")
    raw=metar("KBOS",origin-7*60000)
    rec=p.new_capture(raw,lane="A",seq=0,prev=p.GENESIS,
                      started=origin+60000,ended=origin+62000)
    tampered=deepcopy(rec);tampered["source_body_base64"]="AA=="
    with pytest.raises(p.Refusal):p.verify_capture(tampered)
    forged=deepcopy(rec);forged["global_publisher_first_available_proven"]=True
    with pytest.raises(p.Refusal):p.verify_capture(forged)
    with pytest.raises(p.Refusal,match="source collection"):
        p.new_capture(raw,lane="A",seq=0,prev=p.GENESIS,
            started=p.epoch_ms("2026-11-22T00:00:00Z"),
            ended=p.epoch_ms("2026-11-22T00:00:01Z"))

def test_unsupported_provider_duplicate_or_error_refused():
    origin=p.epoch_ms("2026-11-26T12:00:00Z")
    with pytest.raises(p.Refusal,match="unregistered"):
        p.parse_rows(metar("KSEA",origin-7*60000))
    with pytest.raises(p.Refusal,match="HTTP"):
        p.new_capture(metar("KBOS",origin-7*60000),lane="A",seq=0,
             prev=p.GENESIS,started=origin+30000,ended=origin+31000,status=429)

def test_real_external_anchor_cannot_be_replaced_with_local_self_reporting():
    origin=p.epoch_ms("2026-11-26T12:00:00Z")
    e=fake_capture("A",0,origin+30000,metar("KBOS",origin-7*60000))
    with pytest.raises(p.Refusal,match="independent"):
        p.verify_lanes([e],synthetic_fixture=True)
    forged=deepcopy(e);forged["anchor"].pop("independently_downloaded_from_GitHub")
    with pytest.raises(p.Refusal,match="authenticated"):
        p.verify_lanes([e,forged],synthetic_fixture=True)
    reused=deepcopy(e);reused["record"]["lane"]="B"
    with pytest.raises(p.Refusal):
        p.verify_lanes([e,reused],synthetic_fixture=True)

def test_frozen_two_lane_24hr_history_future_eligible_and_target_separated():
    origin,entries=source_profile()
    streams=p.verify_lanes(entries,synthetic_fixture=True)
    frozen=p.admit_features(streams,station="KBOS",
                            origin_hour_end_ms=origin,horizon_hours=1)
    assert frozen["status"]=="PROSPECTIVE_TWO_EXTERNAL_WITNESS_ADMISSION"
    assert frozen["issue_ms"]==origin+20*60000
    assert not frozen["heldout_target_included"]
    assert not frozen["global_first_publication_attested"]
    assert not frozen["execution_authorized"]
    assert set(frozen["features"])=={"0","1","3","6","24"}
    result=p.target_after_issue(streams,frozen)
    assert abs(result["target_kelvin"]-290.15)<1e-12
    assert set(result["witness_artifacts"])=={"A","B"}

def test_first_seen_after_forecast_issue_is_not_historically_eligible():
    origin,entries=source_profile()
    # Shift external creation times to be after forecast issue (runner falsely
    # claims earlier wall clocks). Capture record/source hashes remain genuine.
    later=deepcopy(entries)
    for e in later:
        e["anchor"]["created_ms"]+=24*p.HOUR
    by=p.verify_lanes(later,synthetic_fixture=True)
    with pytest.raises(p.Refusal,match="before forecast issue"):
        p.admit_features(by,station="KBOS",origin_hour_end_ms=origin,horizon_hours=1)

def test_missing_second_lane_missing_poll_or_source_chain_refused():
    _,entries=source_profile()
    with pytest.raises(p.Refusal,match="independent"):
        p.verify_lanes([e for e in entries if e["record"]["lane"]=="A"],synthetic_fixture=True)
    lost=[e for e in entries if not
          (e["record"]["lane"]=="B" and e["record"]["seq"]==7)]
    with pytest.raises(p.Refusal,match="chain"):
        p.verify_lanes(lost,synthetic_fixture=True)

def test_inconsistent_two_source_workflow_run_ids_refused():
    _,entries=source_profile()
    fake=deepcopy(entries)
    for e in fake:
        if e["record"]["lane"]=="B":
            e["anchor"]["run_id"]=200000+e["record"]["seq"]
    with pytest.raises(p.Refusal,match="same workflow"):
        p.verify_lanes(fake,synthetic_fixture=True)

def test_outside_future_target_guard_does_not_disclose_unfrozen_labels():
    origin,entries=source_profile()
    streams=p.verify_lanes(entries,synthetic_fixture=True)
    original=p.admit_features(streams,station="KBOS",origin_hour_end_ms=origin,horizon_hours=1)
    forged=deepcopy(original);forged["heldout_target_included"]=True
    with pytest.raises(p.Refusal,match="unfrozen"):
        p.target_after_issue(streams,forged)

def test_github_authentication_without_real_token_refused():
    with pytest.raises(p.Refusal,match="token"):
        p.verified_github_capture(145678,token="synthetic")

def test_real_production_mode_refuses_self_asserted_anchor_json_in_place_of_GitHub_fetch():
    origin,entries=source_profile()
    with pytest.raises(p.Refusal,match="independently fetched artifact IDs"):
        p.verify_lanes(entries)
