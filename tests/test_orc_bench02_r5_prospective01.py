"""R5-PROSPECTIVE-01 independent native durable, authorization and external custody tests.

All NOAA responses and GitHub artifacts in this module are synthetic fixtures.
Neither tests nor the GitHub qualification workflow start collection.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import URLError
from zipfile import ZipFile,ZIP_DEFLATED
import json,os,sqlite3,stat
import pytest

from tools.orcbench02 import prospective_r5 as science
from tools.orcbench02 import prospective_r5_durable as d
from tools.orcbench02 import prospective_r5_custody as c

START=science.epoch_ms("2026-11-23T00:00:00Z")
SOURCE_SHA="f"*40
KEY=bytes(range(32))
APPROVAL="BENCH02R5prospective01ApprovedA"
ORIGIN=START+25*science.HOUR

def make_grant(lane="A",start=START,source=SOURCE_SHA):
    body=d.grant_body(lane,start,"fixture-operator",APPROVAL+lane,source)
    return d.sign_grant(body,KEY)

def make_db(tmp_path,lane="A"):
    folder=tmp_path/f"host-{lane}"
    folder.mkdir(mode=0o700,exist_ok=True)
    folder.chmod(0o700)
    g=make_grant(lane)
    return d.Journal(folder/"original-r5.sqlite",lane,{
        k:v for k,v in g.items() if k!="operator_signature_sha256"}),g

def metar(site,when,suffix="normal",temp=15.):
    observation=((when//science.HOUR)*science.HOUR-420000)//1000
    row={"icaoId":site,"obsTime":observation,"rawOb":f"{site} METAR_{observation}_{suffix}",
         "receiptTime":datetime.fromtimestamp(observation+60,timezone.utc).isoformat(),
         "temp":temp}
    return json.dumps([row],sort_keys=True).encode()

def success_fetch(time_ms,site="KBOS",suffix="normal"):
    return lambda:(200,"application/json",metar(site,time_ms,suffix),"Mon, 23 Nov 2026 00:00:00 GMT")

def source_zip(slot):
    buf=BytesIO()
    with ZipFile(buf,"w",ZIP_DEFLATED) as zip:
        zip.writestr("poll.json",json.dumps(slot,sort_keys=True,separators=(",",":")))
    return buf.getvalue()

def meta_for(slot,zipraw,aid,run,source=SOURCE_SHA,created_ms=None):
    if created_ms is None:
        created_ms=START+slot["slot"]*d.PERIOD+60_000
    iso=datetime.fromtimestamp(created_ms/1000,timezone.utc).isoformat()
    return {"id":aid,"expired":False,
            "name":f"orcbench02-r5-poll-{slot['lane']}-{slot['slot']:06d}",
            "digest":"sha256:"+sha256(zipraw).hexdigest(),
            "created_at":iso,
            "workflow_run":{"id":run,"head_sha":source}}

def archived(journal,slot,aid,run):
    item=journal.export_slot(slot);zipraw=source_zip(item)
    return c.authenticate_metadata(meta_for(item,zipraw,aid,run),
            zipraw,artifact_id=aid,source_sha=SOURCE_SHA)

def test_original_R5_science_is_byte_locked_before_operator_session():
    p=d.policy()
    assert d.git_blob(d.CONTRACT.read_bytes())==d.CONTRACT_BLOB
    assert p["operator"]["default_enabled"] is False
    assert p["journal"]["durable_intent_before_network"]
    assert p["native_tests"]["installation_scheduling"].startswith("manual")
    assert science.gitblob(science.PRE.read_bytes())==science.PRE_BLOB

@pytest.mark.parametrize("forgery",["wrong_sig","wrong_lane","expired","wrong_source","wrong_url"])
def test_unsigned_wrong_grant_and_expiration_denied(forgery):
    approved=make_grant()
    if forgery=="wrong_sig":approved["operator_signature_sha256"]="0"*64
    if forgery=="wrong_lane":approved["lane"]="B"
    if forgery=="expired":now=START+d.MAX_SLOTS*d.PERIOD
    if forgery=="wrong_source":approved["locked_original_runtime_source_sha"]="0"*40
    if forgery=="wrong_url":approved["source_url"]="https://example.com/evil"
    with pytest.raises(d.Refusal):
        d.check_grant(approved,KEY,"A",now if forgery=="expired" else START+1000)

def test_bad_key_file_and_posix_permission_refused(tmp_path):
    if os.name!="posix":
        with pytest.raises(d.Refusal,match="Windows"):
            d.secure_posix_key(tmp_path/"nonexistent")
    else:
        keyfile=tmp_path/"operator.key"
        keyfile.write_bytes(KEY);keyfile.chmod(0o644)
        with pytest.raises(d.Refusal,match="0600"):
            d.secure_posix_key(keyfile)
        keyfile.chmod(0o600)
        assert d.secure_posix_key(keyfile)==KEY

def test_successful_once_no_duplicate_replay_and_exact_noaa_body(tmp_path):
    j,grant=make_db(tmp_path)
    try:
        assert d.request_once(j,grant,KEY,START+1000,success_fetch(START))=="OBSERVED"
        events=j.verify_chain()
        assert [e["kind"] for e in events]==["INTENT","OBSERVED"]
        record=events[-1]["payload"]["capture"]
        assert science.verify_capture(record)[0]["site"]=="KBOS"
        assert record["source_sha256"]==sha256(metar("KBOS",START)).hexdigest()
        slot=j.export_slot(0)
        assert len(slot["events"])==2 and slot["terminal_head_sha256"]==events[-1]["event_sha256"]
        with pytest.raises(d.Refusal,match="already attempted"):
            d.request_once(j,grant,KEY,START+2000,success_fetch(START))
    finally:j.close()

def test_durable_crash_restarts_as_interrupted_without_replaying_network(tmp_path):
    j,grant=make_db(tmp_path)
    j.append([{"kind":"INTENT","slot":0,"payload":{"scheduled_start_ms":START,
        "started_ms_untrusted":START+1000,"url":science.URL}}]);j.close()
    j,_=make_db_existing(tmp_path,grant)
    calls=[]
    try:
        result=d.request_once(j,grant,KEY,START+d.PERIOD+1000,
           lambda:(calls.append(1) or (200,"application/json",
                                      metar("KBOS",START+d.PERIOD),"")))
        assert result=="OBSERVED" and calls==[1]
        assert [e["kind"] for e in j.verify_chain()]==[
            "INTENT","INTERRUPTED","INTENT","OBSERVED"]
        assert j.export_slot(0)["events"][-1]["kind"]=="INTERRUPTED"
    finally:j.close()

def make_db_existing(tmp_path,grant):
    lane=grant["lane"]
    body={k:v for k,v in grant.items() if k!="operator_signature_sha256"}
    return d.Journal(tmp_path/f"host-{lane}"/"original-r5.sqlite",lane,body),grant

def test_recovery_records_each_gap_and_late_slot_without_fake_observation(tmp_path):
    j,grant=make_db(tmp_path)
    try:
        attempts=[]
        now=START+4*d.PERIOD+180000
        assert d.request_once(j,grant,KEY,now,lambda:attempts.append(True))=="GAP"
        assert not attempts
        events=j.verify_chain()
        assert [e["kind"] for e in events]==["GAP"]*5
        for index,event in enumerate(events):
            assert event["slot"]==index
            assert event["payload"]["source_observed"] is False
        with pytest.raises(d.Refusal,match="already attempted"):
            d.request_once(j,grant,KEY,now+30000,success_fetch(now))
    finally:j.close()

@pytest.mark.parametrize("bad",["429","invalid_json","wrong_station","network_error"])
def test_http_rate_limit_invalid_source_and_network_failure_are_durable_errors(tmp_path,bad):
    j,grant=make_db(tmp_path)
    def fetch():
        if bad=="429":return 429,"application/json",b'{"retry":"later"}',""
        if bad=="invalid_json":return 200,"application/json",b"no json",""
        if bad=="wrong_station":return 200,"application/json",metar("KSEA",START),""
        raise URLError("synthetic network")
    try:
        assert d.request_once(j,grant,KEY,START+1000,fetch)=="ERROR"
        event=j.verify_chain()[-1]
        assert event["kind"]=="ERROR"
        assert "capture" not in event["payload"]
        assert event["payload"]["reason"] in (
            "HTTP_NON_200","malformed_or_ambiguous_HTTP_200",
            "network_error_no_original_source")
    finally:j.close()

def test_immutable_journal_denies_update_delete_and_approval_replacement(tmp_path):
    j,grant=make_db(tmp_path)
    try:
        d.request_once(j,grant,KEY,START+1000,success_fetch(START))
        with pytest.raises(sqlite3.DatabaseError):
            j.db.execute("UPDATE events SET kind='OBSERVED' WHERE number=0")
        with pytest.raises(sqlite3.DatabaseError):
            j.db.execute("DELETE FROM events")
    finally:j.close()
    other=make_grant("A",START)
    other["approval_id"]="different-operator-authorization"
    other=d.sign_grant({k:v for k,v in other.items() if k!="operator_signature_sha256"},KEY)
    with pytest.raises(d.Refusal,match="different approval"):
        d.Journal(tmp_path/"host-A"/"original-r5.sqlite","A",
                  {k:v for k,v in other.items() if k!="operator_signature_sha256"})

def test_external_sha_timestamp_job_and_zip_must_all_be_authentic(tmp_path):
    j,grant=make_db(tmp_path)
    try:
        d.request_once(j,grant,KEY,START+1000,success_fetch(START))
        slot=j.export_slot(0);zipraw=source_zip(slot)
        base=meta_for(slot,zipraw,100001,900001)
        valid=c.authenticate_metadata(base,zipraw,artifact_id=100001,source_sha=SOURCE_SHA)
        assert valid["anchor"]["authenticated_from_server"]
        for change in ("digest","sha","late_source","name","created_early"):
            forged=deepcopy(base)
            if change=="digest":forged["digest"]="sha256:"+"0"*64
            if change=="sha":forged["workflow_run"]["head_sha"]="0"*40
            if change=="late_source":forged["expired"]=True
            if change=="name":forged["name"]="other-name"
            if change=="created_early":
                forged["created_at"]=datetime.fromtimestamp(
                    (START-10000)/1000,timezone.utc).isoformat()
            with pytest.raises(c.Refusal):
                c.authenticate_metadata(forged,zipraw,artifact_id=100001,
                                        source_sha=SOURCE_SHA)
        with pytest.raises(c.Refusal,match="ZIP"):
            c.read_slot_zip(b"not a real artifact")
    finally:j.close()

def test_unauthenticated_json_is_not_verified_external_two_witness_source():
    with pytest.raises(c.Refusal):
        c.verify_external_series([{"slot":{},"anchor":{}}],approved_sha=SOURCE_SHA)
    with pytest.raises((d.Refusal,FileNotFoundError)):
        d.secure_posix_key(Path("/nonexistent")) if os.name=="posix" else d.secure_posix_key("C:/fake")

def test_two_distinct_runner_archives_and_corrected_report_refusal(tmp_path):
    a,ga=make_db(tmp_path,"A")
    b,gb=make_db(tmp_path,"B")
    try:
        d.request_once(a,ga,KEY,START+1000,success_fetch(START,suffix="A"))
        d.request_once(b,gb,KEY,START+1000,success_fetch(START,suffix="B"))
        x=c.verify_external_series([archived(a,0,100001,900001),
                                    archived(b,0,200001,900002)],
                                   approved_sha=SOURCE_SHA)
        with pytest.raises(c.Refusal,match="corrected"):
            c.audited_first_seen(x,"KBOS",START)
        same=c.authenticate_metadata(meta_for(b.export_slot(0),
            source_zip(b.export_slot(0)),200001,900001),
            source_zip(b.export_slot(0)),artifact_id=200001,
            source_sha=SOURCE_SHA)
        with pytest.raises(c.Refusal,match="two distinct"):
            c.verify_external_series([archived(a,0,100001,900001),same],
                                     approved_sha=SOURCE_SHA)
    finally:a.close();b.close()

def test_full_25_hour_two_witness_source_first_seen_admission_and_future_label_denial(tmp_path):
    a,ga=make_db(tmp_path,"A")
    b,gb=make_db(tmp_path,"B")
    entries=[]
    try:
        for slot in range(152):
            now=START+slot*d.PERIOD+1000
            for lane,j,g,offset in (("A",a,ga,100000),("B",b,gb,200000)):
                result=d.request_once(j,g,KEY,now,success_fetch(now))
                assert result=="OBSERVED"
                entries.append(archived(j,slot,offset+slot,
                                        offset+10000+slot))
        streams=c.verify_external_series(entries,approved_sha=SOURCE_SHA)
        ticket=c.admit_verified_features(streams,station="KBOS",
                                         origin_hour_end_ms=ORIGIN,horizon=1)
        assert ticket["status"]=="SYNCHRONIZED_DUAL_GITHUB_FIRST_SEEN_BEFORE_FORECAST"
        assert set(ticket["features"])=={"0","1","3","6","24"}
        assert not ticket["target_known"]
        assert not ticket["installed_MEL_authorized"]
        assert not ticket["global_publisher_first_publication_proved"]
        # Pinned archive timestamps rather than captured runner wall-clocks
        # decide whether this observation existed before the issue time.
        corrupted=deepcopy(entries)
        for item in corrupted:
            item["anchor"]["created_ms"]+=30*science.HOUR
        shifted=c.verify_external_series(corrupted,approved_sha=SOURCE_SHA)
        with pytest.raises(c.Refusal,match="before forecast issue"):
            c.admit_verified_features(shifted,station="KBOS",
                                      origin_hour_end_ms=ORIGIN,horizon=1)
    finally:a.close();b.close()

def test_missing_archive_slot_or_renumbered_schedule_fails_closed(tmp_path):
    a,ga=make_db(tmp_path,"A")
    b,gb=make_db(tmp_path,"B")
    try:
        for slot in range(3):
            now=START+slot*d.PERIOD+1000
            d.request_once(a,ga,KEY,now,success_fetch(now))
            d.request_once(b,gb,KEY,now,success_fetch(now))
        rows=[archived(j,slot,offset+slot,offset+1000+slot)
              for j,offset in ((a,10000),(b,20000)) for slot in range(3)]
        without=[x for x in rows if not(
            x["slot"]["lane"]=="B" and x["slot"]["slot"]==1)]
        with pytest.raises(c.Refusal,match="missing or reordered"):
            c.verify_external_series(without,approved_sha=SOURCE_SHA)
    finally:a.close();b.close()
