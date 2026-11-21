"""R5: prospective first-SEEN custody, not first public publication.

Production verifier fetches GitHub artifact metadata plus original immutable ZIP
by artifact ID. Test-injected evidence is synthetic, never scientific acceptance.
No background work; network acquisition must be explicitly invoked/authorized.
"""
from __future__ import annotations
from base64 import b64decode,b64encode
from collections import defaultdict
from datetime import datetime,timezone
from hashlib import sha1,sha256
from io import BytesIO
from pathlib import Path
from urllib.request import Request,urlopen
from zipfile import ZipFile
import argparse,json,math,time

ROOT=Path(__file__).resolve().parents[2]
PRE=ROOT/"docs/research/orcgraph/ORCH01E_BENCH02_R5_PREREG.json"
PRE_BLOB="02828d09afaf584a9b5cc8a66e0f2de917b48429"
URL="https://aviationweather.gov/api/data/metar?ids=KBOS,KMSP,KPHX&format=json&hours=2"
GITHUB="https://api.github.com/repos/vjmichael/cognitum/actions/artifacts"
SITES=("KBOS","KMSP","KPHX")
LANES=("A","B")
GENESIS="0"*64
HOUR=3600000

class Refusal(ValueError):pass

def need(ok,why):
    if not ok:raise Refusal(why)

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def sha(x):return sha256(x).hexdigest()
def digest(x):return sha(canonical(x))
def gitblob(b):return sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def epoch_ms(t):
    need(type(t) is str,"UTC timestamp required")
    try:
        d=datetime.fromisoformat(t.replace("Z","+00:00"))
        need(d.tzinfo is not None and d.utcoffset() is not None,"timezone missing")
        return int(d.astimezone(timezone.utc).timestamp()*1000)
    except (ValueError,OverflowError) as e:raise Refusal("invalid UTC timestamp") from e

def prereg():
    b=PRE.read_bytes()
    need(gitblob(b)==PRE_BLOB,"original prospective R5 prereg Git blob changed")
    p=json.loads(b); d=p["prospective_data"]; w=p["witnesses"]
    need(p["schema"]=="cognitum.orcgraph.bench02.r5.prospective_preregistered.v1"
      and d["sites_fixed_order"]==list(SITES) and d["GET_url"]==URL
      and w["lanes_fixed"]==list(LANES)
      and d["feature_lags_hours"]==[0,1,3,6,24]
      and d["forecast_horizons_hours"]==[1,3,6]
      and d["fold_hours"]=={"train":336,"calibration":168,"test":168}
      and d["forecast_issue_offset_minutes_after_hour_end"]==20
      and not w["unattested_global_publisher_first_available_claim"],
      "station/method/fold/source guard changed")
    return p

def parse_rows(raw):
    d=prereg()["prospective_data"]
    need(type(raw) is bytes and 0<len(raw)<=d["max_HTTP_body_bytes"],"source size invalid")
    try:records=json.loads(raw.decode("utf-8"))
    except (ValueError,UnicodeError) as e:raise Refusal("invalid original source JSON") from e
    need(type(records) is list and len(records)<=d["max_METAR_rows_per_poll"],
         "unbounded/nonlist original source")
    out=[]
    for r in records:
        need(type(r) is dict and r.get("icaoId") in SITES,"unregistered source station")
        station=r["icaoId"];obs=r.get("obsTime");report=r.get("rawOb")
        need(type(obs) is int and 946684800<=obs<=4102444800,
             "invalid source observation UTC epoch")
        need(type(report) is str and station in report.split(),"raw METAR identity missing")
        temp=r.get("temp")
        need(temp is None or
             (type(temp) in (int,float) and math.isfinite(temp) and -273.15<temp<100),
             "unqualified Celsius source measurement")
        receipt=r.get("receiptTime")
        need(type(receipt) is str and epoch_ms(receipt)>=obs*1000,
             "invalid provider reported receipt (never publication proof)")
        observed=obs*1000
        out.append(dict(site=station,obs_ms=observed,
                        bucket_end_ms=(observed//HOUR+1)*HOUR,
                        raw_ob=report,temp_c=float(temp) if temp is not None else None,
                        provider_receipt_advisory_ms=epoch_ms(receipt),
                        original_row_sha256=digest(r)))
    return out

def new_capture(raw,*,lane,seq,prev,started,ended,status=200,
                content_type="application/json",http_date=""):
    d=prereg()["prospective_data"]
    need(lane in LANES and type(seq) is int and seq>=0 and
         type(prev) is str and len(prev)==64 and
         all(v in "0123456789abcdef" for v in prev) and
         (seq>0 or prev==GENESIS),"incorrect poll lane or chain")
    need(type(started) is int and type(ended) is int and
         epoch_ms(d["first_start_not_before_utc"])<=started<=ended<=started+60000,
         "invalid source collection start/end")
    need(status==200 and "json" in content_type.lower(),
         "source HTTP refused/not JSON")
    rows=parse_rows(raw)
    need(all(x["obs_ms"]<=ended for x in rows),"future record in provider response")
    rec=dict(schema="cognitum.orc.bench02.r5.capture.v1",
       protocol_git_blob=PRE_BLOB,lane=lane,seq=seq,previous_sha256=prev,
       url=URL,http_status=status,content_type=content_type,
       http_date_advisory=http_date,
       capture_start_ms_untrusted=started,capture_end_ms_untrusted=ended,
       source_sha256=sha(raw),source_body_base64=b64encode(raw).decode("ascii"),
       record_count=len(rows),global_publisher_first_available_proven=False,
       execution_authorized=False)
    rec["record_sha256"]=digest(rec)
    return rec

def verify_capture(r):
    need(type(r) is dict and r.get("schema")=="cognitum.orc.bench02.r5.capture.v1"
       and r.get("url")==URL and r.get("protocol_git_blob")==PRE_BLOB
       and r.get("global_publisher_first_available_proven") is False
       and r.get("execution_authorized") is False,
       "unregistered source/forged publication or MEL grants")
    stamp=r.get("record_sha256")
    need(stamp==digest({k:v for k,v in r.items() if k!="record_sha256"}),
         "original source capture changed")
    try:raw=b64decode(r["source_body_base64"],validate=True)
    except (TypeError,ValueError) as e:raise Refusal("corrupt source encoding") from e
    need(sha(raw)==r["source_sha256"],"original provider response SHA mismatch")
    check=new_capture(raw,lane=r["lane"],seq=r["seq"],prev=r["previous_sha256"],
             started=r["capture_start_ms_untrusted"],ended=r["capture_end_ms_untrusted"],
             status=r["http_status"],content_type=r["content_type"],
             http_date=r["http_date_advisory"])
    need(r==check,"capture is not exactly reproducible")
    return parse_rows(raw)

def _github_get(url,token):
    need(type(token) is str and len(token)>10,"GitHub evidence lookup token required")
    request=Request(url,headers={"Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"Cognitum-R5-independent-witness/1.0"})
    with urlopen(request,timeout=20) as response:
        need(response.status==200,"independent GitHub evidence lookup failed")
        value=response.read(5_000_001)
    need(len(value)<=5_000_000,"oversized independent Github evidence")
    return value

def verified_github_capture(artifact_id,*,token):
    """Download trusted GitHub metadata and exact immutable ZIP; no self-attestation."""
    need(type(artifact_id) is int and artifact_id>0,"concrete GitHub artifact ID required")
    meta=json.loads(_github_get(f"{GITHUB}/{artifact_id}",token))
    run=(meta.get("workflow_run") or {}).get("id")
    need(meta.get("id")==artifact_id and meta.get("expired") is False
      and meta.get("name","").startswith("orcbench02-r5-capture-")
      and type(run) is int,"GitHub artifact/run not independently authenticated")
    archive=_github_get(f"{GITHUB}/{artifact_id}/zip",token)
    if meta.get("digest"):
        need(meta["digest"]=="sha256:"+sha(archive),
             "independent original GitHub ZIP digest mismatch")
    try:
        with ZipFile(BytesIO(archive)) as z:
            need(z.namelist()==["capture.json"] and z.testzip() is None,
                 "not a single original capture in GitHub ZIP")
            record=json.loads(z.read("capture.json"))
    except Exception as e:raise Refusal("invalid original GitHub artifact") from e
    verify_capture(record)
    need(meta["name"]==f"orcbench02-r5-capture-{record['lane']}-{record['seq']:06d}",
         "external GitHub source lane/sequence mismatch")
    created=epoch_ms(meta["created_at"])
    need(record["capture_end_ms_untrusted"]<=created,
         "original capture claims occur after trusted external archive timestamp")
    return dict(record=record,anchor=dict(id=artifact_id,run_id=run,
        created_ms=created,archive_sha256=sha(archive),
        independently_downloaded_from_GitHub=True))

def verify_lanes(entries, *, token=None, synthetic_fixture=False):
    """Production requires concrete IDs and independent GitHub API/ZIP reads.

    Explicit synthetic_fixture is for isolated unit tests only, and cannot
    attest NOAA, GitHub availability or the original collection process.
    """
    if not synthetic_fixture:
        need(type(entries) is list and all(type(v) is int for v in entries),
             "production source must be independently fetched artifact IDs")
        entries=[verified_github_capture(v,token=token) for v in entries]
    need(type(entries) is list and len(entries)>=2,
         "both original independent source observers required")
    lanes=defaultdict(list);artifact_ids=set();runs=defaultdict(set)
    for x in entries:
        need(type(x) is dict and x.get("anchor",{}).get(
            "independently_downloaded_from_GitHub") is True,
            "not authenticated independent GitHub artifact")
        r=x["record"];a=x["anchor"];verify_capture(r)
        need(type(a["id"]) is int and type(a["run_id"]) is int
           and type(a["created_ms"]) is int and
           type(a["archive_sha256"]) is str and len(a["archive_sha256"])==64
           and a["created_ms"]>=r["capture_end_ms_untrusted"]
           and a["id"] not in artifact_ids,
           "replayed/impossible original external anchor")
        artifact_ids.add(a["id"]);runs[r["seq"]].add(a["run_id"])
        lanes[r["lane"]].append(x)
    need(set(lanes)==set(LANES),"not two independent original lanes")
    for lane in LANES:
        previous=GENESIS;last=None;series=sorted(lanes[lane],key=lambda x:x["record"]["seq"])
        for index,x in enumerate(series):
            r=x["record"]
            need(r["seq"]==index and r["previous_sha256"]==previous,
                 "source polling chain missing or rewritten")
            if last is not None:
                delta=r["capture_start_ms_untrusted"]-last
                need(600000<=delta<=25*60000,
                     "original poll gap or overfrequent NOAA request refused")
            previous=r["record_sha256"];last=r["capture_start_ms_untrusted"]
        lanes[lane]=series
    need(all(len(v)>=2 for v in runs.values()),
         "same workflow run or missing one source witness")
    return lanes

def first_seen(lanes,site,bucket_end):
    candidates={}
    for lane,entries in lanes.items():
        for e in entries:
            for record in verify_capture(e["record"]):
                if record["site"]!=site or record["bucket_end_ms"]!=bucket_end:
                    continue
                key=(record["raw_ob"],record["obs_ms"],record["temp_c"],
                     record["original_row_sha256"])
                candidates.setdefault(key,{}).setdefault(lane,[]).append(e["anchor"])
    need(len(candidates)==1,"missing, duplicated or corrected original station-hour")
    row,sightings=next(iter(candidates.items()))
    need(row[2] is not None and all(lane in sightings for lane in LANES),
         "not one finite observation with two independently anchored witnesses")
    first={lane:min(sightings[lane],key=lambda x:x["created_ms"]) for lane in LANES}
    need(first["A"]["id"]!=first["B"]["id"] and
         first["A"]["run_id"]!=first["B"]["run_id"],
         "not two separate independent witness executions")
    return row,first

def admit_features(lanes,*,station,origin_hour_end_ms,horizon_hours):
    d=prereg()["prospective_data"]
    need(station in SITES and horizon_hours in (1,3,6) and
         type(origin_hour_end_ms) is int and origin_hour_end_ms%HOUR==0,
         "unregistered original station/time/horizon")
    issued=origin_hour_end_ms+20*60000
    features={}
    for lag in d["feature_lags_hours"]:
        bucket=origin_hour_end_ms-lag*HOUR
        obs,anchors=first_seen(lanes,station,bucket)
        need(obs[1]<issued and all(v["created_ms"]<=issued for v in anchors.values()),
             "original feature not externally archived before forecast issue")
        features[str(lag)]={"bucket_end_ms":bucket,
            "artifact_ids":{lane:a["id"] for lane,a in anchors.items()},
            "observation_sha256":digest(obs)}
    return dict(status="PROSPECTIVE_TWO_EXTERNAL_WITNESS_ADMISSION",
       station=station,origin_hour_end_ms=origin_hour_end_ms,
       issue_ms=issued,horizon_hours=horizon_hours,
       target_hour_end_ms=origin_hour_end_ms+horizon_hours*HOUR,
       features=features,heldout_target_included=False,
       global_first_publication_attested=False,execution_authorized=False)

def target_after_issue(lanes,admission):
    need(admission["status"]=="PROSPECTIVE_TWO_EXTERNAL_WITNESS_ADMISSION"
         and admission["heldout_target_included"] is False,
         "unfrozen or future-leaking target")
    row,anchors=first_seen(lanes,admission["station"],
                           admission["target_hour_end_ms"])
    need(row[1]>admission["issue_ms"] and
         all(v["created_ms"]>admission["issue_ms"] for v in anchors.values()),
         "forecast target existed before locked forecast issue")
    return {"target_kelvin":row[2]+273.15,"obs_ms":row[1],
            "witness_artifacts":{lane:a["id"] for lane,a in anchors.items()}}

def capture_once(lane,seq,prev,dest):
    p=prereg()["prospective_data"];start=time.time_ns()//1_000_000
    req=Request(URL,headers={"User-Agent":p["http_user_agent"],
                             "Accept":"application/json"})
    with urlopen(req,timeout=15) as http:
        status=http.status;type_=http.headers.get("Content-Type","")
        date=http.headers.get("Date","")
        raw=http.read(p["max_HTTP_body_bytes"]+1)
    end=time.time_ns()//1_000_000
    rec=new_capture(raw,lane=lane,seq=seq,prev=prev,started=start,ended=end,
                    status=status,content_type=type_,http_date=date)
    with Path(dest).open("x",encoding="utf-8",newline="\n") as file:
        json.dump(rec,file,indent=2,sort_keys=True);file.write("\n")
    print(json.dumps({"lane":lane,"seq":seq,"sha256":rec["record_sha256"],
           "original_body_sha256":rec["source_sha256"],
           "global_publisher_first_publication_proven":False}))

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--lane",choices=LANES,required=True)
    cli.add_argument("--seq",type=int,required=True)
    cli.add_argument("--previous",default=GENESIS)
    cli.add_argument("--output",required=True)
    a=cli.parse_args()
    capture_once(a.lane,a.seq,a.previous,a.output)
if __name__=="__main__":main()
