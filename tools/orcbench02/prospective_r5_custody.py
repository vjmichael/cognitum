"""R5-PROSPECTIVE-01: externally authenticated Github original-poll archive.

Works with ZIP downloaded through supported actions/download-artifact, not the
direct REST ZIP redirect that failed HTTP 401 in original R5 acceptance.
Production authenticates artifact metadata separately using REST and pins its
original workflow source SHA and GitHub timestamp. No self-supplied metadata
dict establishes trusted provider authority.
"""
from __future__ import annotations
from base64 import b64decode
from collections import defaultdict
from datetime import datetime,timezone
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile,BadZipFile
from urllib.request import Request,urlopen
import json

from tools.orcbench02 import prospective_r5 as old
from tools.orcbench02 import prospective_r5_durable as durable

MAX_ARCHIVE=5_000_000
MAX_JSON=3_500_000
REPOSITORY_ID_REQUIRED=True

class Refusal(ValueError):pass
def need(ok,why):
    if not ok:raise Refusal(why)

def read_slot_zip(raw):
    need(type(raw) is bytes and 0<len(raw)<=MAX_ARCHIVE,
         "GitHub original archive absent or oversized")
    try:
        with ZipFile(BytesIO(raw)) as z:
            infos=z.infolist()
            need(len(infos)==1 and infos[0].filename=="poll.json" and
                 infos[0].file_size<=MAX_JSON and z.testzip() is None,
                 "GitHub original poll ZIP must contain one unmodified poll.json")
            data=z.read("poll.json")
    except (BadZipFile,KeyError,RuntimeError) as e:
        raise Refusal("GitHub original poll ZIP malformed") from e
    need(len(data)<=MAX_JSON,"original poll too large")
    try:return json.loads(data)
    except (ValueError,UnicodeError) as e:raise Refusal("poll source invalid JSON") from e

def authenticate_metadata(metadata,archive,*,artifact_id,source_sha):
    """Pure cryptographic checks; production must use fetch_github_metadata."""
    need(type(metadata) is dict and type(artifact_id) is int and artifact_id>0,
         "trusted external GitHub artifact ID required")
    need(type(source_sha) is str and len(source_sha)==40,
         "approved original runtime code SHA required")
    run=metadata.get("workflow_run") or {}
    need(metadata.get("id")==artifact_id and metadata.get("expired") is False
       and isinstance(metadata.get("name"),str)
       and metadata.get("name","").startswith("orcbench02-r5-poll-")
       and run.get("head_sha")==source_sha and
       type(run.get("id")) is int and run["id"]>0,
       "artifact not produced by exact approved original workflow source")
    digest=sha256(archive).hexdigest()
    need(metadata.get("digest")=="sha256:"+digest,
         "GitHub independent archive SHA256 does not match original ZIP")
    read=read_slot_zip(archive)
    need(read.get("schema")=="cognitum.orc.bench02.r5.prospective01.slot.v1"
        and read.get("external_GitHub_artifact_not_yet_proven") is True
        and read.get("lane") in old.LANES
        and type(read.get("slot")) is int and 0<=read["slot"]<durable.MAX_SLOTS,
        "invalid original journal slot evidence")
    need(metadata.get("name")==
         f"orcbench02-r5-poll-{read['lane']}-{read['slot']:06d}",
         "GitHub original artifact name mismatches signed lane/slot")
    created=old.epoch_ms(metadata["created_at"])
    verify_slot(read)
    first=read["events"][0]
    local_start=first["payload"].get("started_ms_untrusted",
                 first["payload"].get("discovered_at_ms_untrusted"))
    need(type(local_start) is int and created+999>=local_start,
         "GitHub artifact created before local original attempt/gap discovery")
    if read["events"][-1]["kind"]=="OBSERVED":
        capture=read["events"][-1]["payload"]["capture"]
        need(created+999>=capture["capture_end_ms_untrusted"],
             "GitHub artifact timestamp predates NOAA response completion")
    return {"slot":read,"anchor":{
        "artifact_id":artifact_id,
        "run_id":run["id"],
        "source_sha":source_sha,
        "created_ms":created,
        "zip_sha256":digest,
        "authenticated_from_server":True}}

def fetch_github_metadata(artifact_id,token):
    need(type(token) is str and len(token)>10,
         "independent GitHub API credential required")
    url=f"https://api.github.com/repos/vjmichael/cognitum/actions/artifacts/{artifact_id}"
    request=Request(url,headers={
       "Authorization":"Bearer "+token,
       "Accept":"application/vnd.github+json",
       "X-GitHub-Api-Version":"2022-11-28",
       "User-Agent":"Cognitum-R5-two-independent-original-source-witnesses"})
    with urlopen(request,timeout=20) as response:
        need(response.status==200,"GitHub original artifact metadata authentication failed")
        data=response.read(100001)
    need(len(data)<=100000,"GitHub artifact metadata oversized")
    return json.loads(data)

def verified_external_slot(artifact_id,archive,*,token,source_sha):
    """Production entry: NEVER accepts unauthenticated caller metadata."""
    meta=fetch_github_metadata(artifact_id,token)
    return authenticate_metadata(meta,archive,artifact_id=artifact_id,source_sha=source_sha)

def verify_slot(slot):
    need(type(slot) is dict and
         slot.get("schema")=="cognitum.orc.bench02.r5.prospective01.slot.v1"
         and slot.get("lane") in old.LANES,
         "slot schema/lane missing")
    rows=slot.get("events");seq=slot.get("slot")
    need(type(rows) is list and 1<=len(rows)<=2 and
         all(type(x) is dict for x in rows),
         "original slot not a completed immutable poll event")
    kinds=[x["kind"] for x in rows]
    need(kinds==["GAP"] or (kinds[0]=="INTENT" and
         kinds[1] in ("OBSERVED","ERROR","INTERRUPTED")),
         "incomplete or fabricated source attempt")
    prev=slot["prior_head_sha256"]
    for i,event in enumerate(rows):
        need(event["schema"]==durable.SCHEMA
             and event["lane"]==slot["lane"] and event["slot"]==seq
             and event["prior_sha256"]==prev
             and event["event_sha256"]==durable.digest(
                  {k:v for k,v in event.items() if k!="event_sha256"}),
             "original source poll cryptographic event chain broken")
        prev=event["event_sha256"]
    need(prev==slot["terminal_head_sha256"],
         "externally anchored source terminal head mismatch")
    last=rows[-1]
    if last["kind"]=="OBSERVED":
        capture=last["payload"]["capture"]
        old.verify_capture(capture)
        need(capture["lane"]==slot["lane"] and
             capture["seq"]==seq,
             "original successful NOAA response from another slot")
    else:
        need("capture" not in last["payload"],
             "refused/source-error slot contains fictitious observation")
    return last["kind"]

def verify_external_series(entries,*,approved_sha):
    """Exact independent source identity, gap visibility and no clock backfill."""
    need(type(entries) is list and len(entries)>=2,
         "two independent external source lanes required")
    by_lane=defaultdict(list);all_ids=set();all_runs=defaultdict(set)
    for entry in entries:
        need(type(entry) is dict and entry.get("anchor",{}).get(
            "authenticated_from_server") is True and
            entry["anchor"]["source_sha"]==approved_sha,
            "unverified independent external artifact")
        slot=entry["slot"];anchor=entry["anchor"]
        verify_slot(slot)
        need(type(anchor["artifact_id"]) is int and
             anchor["artifact_id"] not in all_ids and
             type(anchor["created_ms"]) is int and
             type(anchor["run_id"]) is int and
             anchor["created_ms"]>0,
             "replayed or unanchored original GitHub artifact")
        all_ids.add(anchor["artifact_id"])
        all_runs[slot["slot"]].add(anchor["run_id"])
        by_lane[slot["lane"]].append(entry)
    need(set(by_lane)==set(old.LANES),"missing one separately authenticated source lane")
    first_grants=set()
    for lane in old.LANES:
        series=sorted(by_lane[lane],key=lambda x:x["slot"]["slot"])
        prev=old.GENESIS
        grant=None
        expected_number=0
        activation=None
        for idx,entry in enumerate(series):
            slot=entry["slot"]
            need(slot["slot"]==idx and slot["prior_head_sha256"]==prev
              and slot["events"][0]["number"]==expected_number,
              "missing or reordered externally archived scheduled slot")
            first=slot["events"][0]
            scheduled=first["payload"]["scheduled_start_ms"]
            if activation is None:
                activation=scheduled
                need(activation%durable.PERIOD==0,
                     "source operator activation was not on an original 10-minute slot")
            need(scheduled==activation+idx*durable.PERIOD,
                 "source schedule skipped or fabricated a planned 10-minute slot")
            if first["kind"]=="INTENT":
                started=first["payload"]["started_ms_untrusted"]
                need(scheduled<=started<=scheduled+durable.MAX_DELAY,
                     "original source attempt outside operator-approved slot")
            for n,ev in enumerate(slot["events"]):
                need(ev["number"]==expected_number+n,
                     "event numbering reordered despite valid poll slots")
            expected_number+=len(slot["events"])
            prev=slot["terminal_head_sha256"]
            if grant is None:grant=slot["grant_identity_sha256"]
            need(grant==slot["grant_identity_sha256"],
                 "source operator approval changed mid-study")
        first_grants.add((lane,grant))
        by_lane[lane]=series
    need(all(len(ids)==2 for ids in all_runs.values()),
         "each original slot must have two distinct native workflow runs")
    return by_lane

def audited_first_seen(by_lane,station,bucket_end):
    """All archived source corrections count; never select favorable NOAA variant."""
    candidates={}
    for lane,entries in by_lane.items():
        for item in entries:
            slot=item["slot"]
            if verify_slot(slot)!="OBSERVED":continue
            capture=slot["events"][-1]["payload"]["capture"]
            for record in old.verify_capture(capture):
                if record["site"]!=station or record["bucket_end_ms"]!=bucket_end:
                    continue
                key=(record["raw_ob"],record["obs_ms"],record["temp_c"],
                     record["original_row_sha256"])
                candidates.setdefault(key,{}).setdefault(lane,[]).append(item["anchor"])
    need(len(candidates)==1,
         "missing, duplicated or corrected source station-hour")
    record,sightings=next(iter(candidates.items()))
    need(record[2] is not None and all(k in sightings for k in old.LANES),
         "source missing Celsius or only one independent witness")
    first={lane:min(sightings[lane],key=lambda e:e["created_ms"])
           for lane in old.LANES}
    need(first["A"]["run_id"]!=first["B"]["run_id"] and
         first["A"]["artifact_id"]!=first["B"]["artifact_id"],
         "same original source run is not two independent witnesses")
    return record,first

def admit_verified_features(by_lane,*,station,origin_hour_end_ms,horizon):
    """Never issues a model forecast or releases a target to the evaluator."""
    policy=old.prereg()["prospective_data"]
    need(station in old.SITES and horizon in (1,3,6) and
         type(origin_hour_end_ms) is int and
         origin_hour_end_ms%old.HOUR==0,
         "unregistered source forecast origin/horizon")
    issued=origin_hour_end_ms+20*60000
    earliest=origin_hour_end_ms-24*old.HOUR
    # A gap/error in any expected 10-minute slot in feature history is a
    # scientific abstention, not an implicit clean observation interval.
    for lane,series in by_lane.items():
        for item in series:
            slot=item["slot"];starting=slot["events"][0]["payload"].get(
                "scheduled_start_ms")
            if starting is None:continue
            if earliest<=starting<=issued:
                need(verify_slot(slot)=="OBSERVED",
                     "source outage/error observed within fixed 24-hour lag window")
    features={}
    for lag in policy["feature_lags_hours"]:
        bucket=origin_hour_end_ms-lag*old.HOUR
        observed,anchors=audited_first_seen(by_lane,station,bucket)
        need(observed[1]<issued and
             all(anchor["created_ms"]<=issued-1000 for anchor in anchors.values()),
             "feature not independently archived before forecast issue")
        features[str(lag)]={"original_bucket_end_ms":bucket,
            "original_source_row_sha256":observed[3],
            "authenticated_GitHub_artifact_ids":{
                lane:anchors[lane]["artifact_id"] for lane in old.LANES}}
    return {
        "status":"SYNCHRONIZED_DUAL_GITHUB_FIRST_SEEN_BEFORE_FORECAST",
        "site":station,"origin_hour_end_ms":origin_hour_end_ms,
        "issue_ms":issued,"target_hour_end_ms":origin_hour_end_ms+horizon*old.HOUR,
        "horizon":horizon,"features":features,
        "target_known":False,"global_publisher_first_publication_proved":False,
        "installed_MEL_authorized":False}
