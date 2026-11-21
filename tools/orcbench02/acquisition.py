"""BENCH-02-R2: bounded original NOAA AWC capture and revision-preserving journal.

A provider receipt timestamp and local capture timestamp are NOT proof of
historical public availability. All output is research-only and ungated for MEL.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import ssl
import stat
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
from tools.orcbench02.availability_gate import SourceRefusal, require, receipt_ms

MAX_BODY=2_000_000
MAX_ROWS=400
STATIONS=("KMCI",)
ORIGIN="https://aviationweather.gov"
SCHEMA="cognitum.orc.bench02.capture.r2.v1"

def canonical(v):
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True,
                      allow_nan=False).encode("utf-8")

def hash_json(v):
    return sha256(canonical(v)).hexdigest()

def source_url(station):
    require(station in STATIONS,"unapproved station")
    return ORIGIN+"/api/data/metar?ids="+station+"&format=json&hours=3"

def parse_json(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError,ValueError) as e:
        raise SourceRefusal("invalid original-source JSON") from e

def parse_rows(raw,station,finished_ms):
    require(type(raw) is bytes and 2<=len(raw)<=MAX_BODY,"oversized/empty source")
    require(station in STATIONS and type(finished_ms) is int and finished_ms>0,
            "station/capture boundary")
    rows=parse_json(raw)
    require(type(rows) is list and 0<len(rows)<=MAX_ROWS,"provider row limit")
    result=[]
    for index,row in enumerate(rows):
        require(type(row) is dict and row.get("icaoId")==station,
                f"row {index}: station mismatch")
        obs=row.get("obsTime")
        require(type(obs) is int and 946684800<=obs<=4102444800,
                f"row {index}: invalid obsTime")
        received=receipt_ms(row.get("receiptTime"))
        require(obs*1000<=received<=finished_ms,
                f"row {index}: observation/receipt/capture time contradiction")
        report=row.get("rawOb")
        require(type(report) is str and station in report.split(),
                f"row {index}: original report missing/station mismatch")
        temp=row.get("temp")
        require(temp is None or
                (type(temp) in (float,int) and math.isfinite(temp) and temp+273.15>0),
                f"row {index}: invalid temperature")
        result.append({
            "row_index":index,"observed_ms":obs*1000,
            "awc_receipt_ms":received,"raw_report":report,
            "raw_report_sha256":sha256(report.encode("utf-8")).hexdigest(),
            "original_record_sha256":hash_json(row),
            "temperature_k":None if temp is None else float(temp)+273.15,
        })
    return result

def safe_root(path):
    root=Path(path)
    require(not root.is_symlink(),"symlink root refused")
    if not root.exists():
        root.mkdir(mode=0o700,parents=False)
    require(root.is_dir() and not root.is_symlink(),"invalid journal directory")
    if os.name=="posix":
        os.chmod(root,0o700)
        require(stat.S_IMODE(root.stat().st_mode)==0o700,"unprotected journal root")
    return root

def raw_path(root,filename):
    require(type(filename) is str and filename.startswith("snapshot-") and
            filename.endswith(".json") and "/" not in filename and
            "\\" not in filename and ".." not in filename,"unsafe snapshot path")
    path=root/filename
    require(not path.is_symlink(),"symlink snapshot refused")
    return path

def write_once(path,content):
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
    if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
    descriptor=os.open(path,flags,0o600)
    with os.fdopen(descriptor,"wb") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    if os.name=="posix":
        require(stat.S_IMODE(path.stat().st_mode)==0o600,"unprotected evidence file")

def verify_journal(root):
    root=Path(root)
    if not root.exists():return []
    require(root.is_dir() and not root.is_symlink(),"unqualified evidence root")
    if os.name=="posix":
        require(stat.S_IMODE(root.stat().st_mode)==0o700,
                "unprotected evidence directory")
    paths=sorted(root.glob("receipt-*.json"))
    entries=[]
    seen={}
    for number,path in enumerate(paths,1):
        require(not path.is_symlink() and path.name==f"receipt-{number:06d}.json",
                "noncontiguous/replaced receipt")
        entry=parse_json(path.read_bytes())
        require(type(entry) is dict and entry.get("schema")==SCHEMA and
                entry.get("sequence")==number,"invalid receipt record")
        expected=entry.get("entry_sha256")
        unsigned={k:v for k,v in entry.items() if k!="entry_sha256"}
        require(expected==hash_json(unsigned),"altered receipt digest")
        require(entry.get("previous_sha256")==(
            entries[-1]["entry_sha256"] if entries else None),"broken journal chain")
        require(type(entry.get("started_ms")) is int and
                type(entry.get("finished_ms")) is int and
                0<entry["started_ms"]<=entry["finished_ms"] and
                (not entries or entry["started_ms"]>=entries[-1]["started_ms"]),
                "inconsistent capture clock")
        station=entry.get("station")
        require(entry.get("url")==source_url(station),"source endpoint switched")
        original=raw_path(root,entry.get("raw_filename")).read_bytes()
        require(sha256(original).hexdigest()==entry.get("source_sha256") and
                len(original)==entry.get("source_bytes"),"source bytes changed/missing")
        parsed=parse_rows(original,station,entry["finished_ms"])
        history=entry.get("versions")
        require(type(history) is list and len(history)==len(parsed),
                "lost original revisions")
        for row,record in zip(parsed,history):
            require(all(row[k]==record.get(k) for k in row),"revised row modified")
            key=(station,row["observed_ms"],row["original_record_sha256"])
            preceding=seen.get(key)
            expected_first=(preceding if preceding is not None else entry["finished_ms"])
            require(record.get("first_seen_ms")==expected_first,"forged first-seen")
            prior_revisions=any(k[:2]==key[:2] and k[2]!=key[2] for k in seen)
            require(record.get("is_revision")==prior_revisions,
                    "revision history mismatch")
            if preceding is None:seen[key]=entry["finished_ms"]
        entries.append(entry)
    require(sorted(p.name for p in root.glob("snapshot-*.json"))==
            [x["raw_filename"] for x in entries],"unpaired original snapshot")
    return entries

def save_snapshot(root,station,url,raw,started_ms,finished_ms,
                  server_date,content_type,capture_context):
    require(url==source_url(station),"unapproved request URL")
    require(type(started_ms) is int and type(finished_ms) is int and
            0<started_ms<=finished_ms,"capture clock")
    require(type(capture_context) is str and len(capture_context)>=12,
            "missing independently cross-checkable run context")
    parsed=parse_rows(raw,station,finished_ms)
    root=safe_root(root)
    earlier=verify_journal(root)
    require(not earlier or started_ms>=earlier[-1]["started_ms"],
            "replayed capture clock")
    seen={}
    for snapshot in earlier:
        for item in snapshot["versions"]:
            key=(snapshot["station"],item["observed_ms"],item["original_record_sha256"])
            seen.setdefault(key,item["first_seen_ms"])
    versions=[]
    for row in parsed:
        key=(station,row["observed_ms"],row["original_record_sha256"])
        prior=seen.get(key)
        item=dict(row,first_seen_ms=(prior if prior is not None else finished_ms),
                  is_revision=any(k[:2]==key[:2] and k[2]!=key[2] for k in seen))
        if prior is None:seen[key]=finished_ms
        versions.append(item)
    number=len(earlier)+1
    name=f"snapshot-{number:06d}.json"
    record={
        "schema":SCHEMA,"sequence":number,
        "previous_sha256":earlier[-1]["entry_sha256"] if earlier else None,
        "station":station,"url":url,"source_sha256":sha256(raw).hexdigest(),
        "source_bytes":len(raw),"raw_filename":name,
        "started_ms":started_ms,"finished_ms":finished_ms,
        "server_http_date":server_date,"provider_content_type":content_type,
        "capture_context":capture_context,
        "transport":"SYSTEM_CA_HTTPS_NO_REDIRECT",
        "host_clock_attested":False,"historical_public_availability_verified":False,
        "production_authorized":False,"versions":versions,
    }
    record["entry_sha256"]=hash_json(record)
    # A crash between these exclusive writes produces an orphan: verification refuses.
    write_once(raw_path(root,name),raw)
    write_once(root/f"receipt-{number:06d}.json",canonical(record)+b"\n")
    require(verify_journal(root)[-1]==record,"postwrite verification mismatch")
    return record

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise SourceRefusal("redirected source refused")

def download(station,*,opener=None,clock=None):
    url=source_url(station)
    opener=opener or build_opener(
        HTTPSHandler(context=ssl.create_default_context()),NoRedirect())
    clock=clock or (lambda:int(time.time_ns()//1_000_000))
    started=clock()
    req=Request(url,method="GET",headers={
        "User-Agent":"Cognitum-Orc-BENCH02/1.0 (github.com/vjmichael/cognitum)",
        "Accept":"application/json","Cache-Control":"no-cache"})
    try:
        with opener.open(req,timeout=20) as response:
            require(response.status==200,"unavailable HTTP response")
            content_type=response.headers.get("Content-Type","")
            require("application/json" in content_type.lower(),
                    "provider did not supply JSON")
            original=response.read(MAX_BODY+1)
            date=response.headers.get("Date","")
    except (HTTPError,URLError,OSError,TimeoutError) as exc:
        raise SourceRefusal("real source network capture refused") from exc
    finished=clock()
    require(started<=finished,"backwards acquisition clock")
    parse_rows(original,station,finished)
    return dict(station=station,url=url,raw=original,
                started_ms=started,finished_ms=finished,
                server_date=date,content_type=content_type)

def research_asof(entries,origin_ms):
    require(type(origin_ms) is int and origin_ms>0,"invalid origin")
    output=[];seen=set()
    for entry in entries:
        require(entry["production_authorized"] is False,"untrusted production claim")
        for item in entry["versions"]:
            ident=(entry["station"],item["observed_ms"],item["original_record_sha256"])
            if ident not in seen:
                seen.add(ident)
                if (item["observed_ms"]<=origin_ms and
                    item["awc_receipt_ms"]<=origin_ms and
                    item["first_seen_ms"]<=origin_ms):
                    output.append(item)
    return output

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--station",choices=STATIONS,default="KMCI")
    ap.add_argument("--output",required=True)
    ap.add_argument("--context",required=True)
    args=ap.parse_args()
    require(args.context.startswith("github-run:") and len(args.context)>=18,
            "run context required")
    received=download(args.station)
    receipt=save_snapshot(args.output,capture_context=args.context,**received)
    print(json.dumps({"status":"CAPTURED_RESEARCH_ONLY",
        "source_sha256":receipt["source_sha256"],"entry_sha256":receipt["entry_sha256"],
        "source_bytes":receipt["source_bytes"],"rows":len(receipt["versions"]),
        "started_ms":receipt["started_ms"],"finished_ms":receipt["finished_ms"],
        "historical_public_availability_verified":False,
        "production_authorized":False},sort_keys=True))

if __name__=="__main__":
    main()
