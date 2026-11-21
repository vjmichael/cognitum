"""R5-PROSPECTIVE-01: durable, fail-closed, operator-granted NOAA polling.

No service/cron is installed by this module. Each invocation performs AT MOST
one source GET and records all previous missed 10-minute slots as GAP.
The original R5 method source and preregistration are never changed.
"""
from __future__ import annotations
from base64 import b64encode
from contextlib import contextmanager
from hashlib import sha256,sha1
from hmac import compare_digest,new as hmac_new
from pathlib import Path
import json,os,sqlite3,stat,time
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

from tools.orcbench02 import prospective_r5 as p

ROOT=Path(__file__).resolve().parents[2]
CONTRACT=ROOT/"docs/research/orcgraph/ORCH01E_BENCH02_R5_PROSPECTIVE01_PREREG.json"
CONTRACT_BLOB="4329f1e3281c7a7590cec5720dbca6a0c77c6e7f"
SCHEMA="cognitum.orc.bench02.r5.prospective01.journal.v1"
GRANT_SCHEMA="cognitum.orc.bench02.r5.prospective01.grant.v1"
PERIOD=600000
MAX_SLOTS=4032
MAX_DELAY=120000
MAX_RESPONSE=2_000_000

class Refusal(ValueError):pass

def require(valid,reason):
    if not valid:raise Refusal(reason)

def canonical(x):return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
def digest(x):return sha256(canonical(x)).hexdigest()
def git_blob(raw):return sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def policy():
    b=CONTRACT.read_bytes()
    require(git_blob(b)==CONTRACT_BLOB,"operator journal protocol Git source lock broken")
    q=json.loads(b)
    require(q["schema"]=="cognitum.orc.bench02.r5.prospective01.operator_custody.v1"
            and q["parents"]["R5_prereg_git_blob"]==p.PRE_BLOB
            and q["immutable_science"]["interval_seconds"]==600
            and q["journal"]["durable_intent_before_network"] is True
            and q["operator"]["default_enabled"] is False
            and q["external_custody"]["one_archived_poll_per_lane_per_slot"],
            "operator/custody acceptance rules altered")
    p.prereg()
    return q

def grant_body(lane,start_ms,operator_id,approval_id,source_sha):
    policy()
    require(lane in p.LANES and
            type(start_ms) is int and start_ms % PERIOD==0 and
            start_ms>=p.epoch_ms(p.prereg()["prospective_data"]["first_start_not_before_utc"]) and
            type(operator_id) is str and 2<=len(operator_id)<=100 and
            type(approval_id) is str and 16<=len(approval_id)<=128 and
            type(source_sha) is str and len(source_sha)==40 and
            all(x in "0123456789abcdef" for x in source_sha),
            "invalid explicit time-bounded lane/operator authority")
    return {
        "schema":GRANT_SCHEMA,"protocol_git_blob":CONTRACT_BLOB,
        "R5_prereg_git_blob":p.PRE_BLOB,"source_url":p.URL,
        "lane":lane,"operator_id":operator_id,"approval_id":approval_id,
        "starts_ms":start_ms,"expires_ms":start_ms+MAX_SLOTS*PERIOD,
        "interval_ms":PERIOD,"max_slots":MAX_SLOTS,
        "capability":"single fixed NOAA GET per 10-minute slot",
        "no_installed_service":True,"locked_original_runtime_source_sha":source_sha
    }

def sign_grant(body,key):
    require(type(key) is bytes and len(key)>=32,
            "operator signing key must be >=256 bits")
    return {**body,"operator_signature_sha256":
        hmac_new(key,canonical(body),"sha256").hexdigest()}

def check_grant(grant,key,lane,now_ms):
    policy()
    require(type(grant) is dict and type(now_ms) is int,
            "operator approval and local clock required")
    sig=grant.get("operator_signature_sha256")
    body={k:v for k,v in grant.items() if k!="operator_signature_sha256"}
    require(type(sig) is str and len(sig)==64
       and compare_digest(sig,hmac_new(key,canonical(body),"sha256").hexdigest()),
       "invalid operator authorization signature")
    expected=grant_body(body.get("lane"),body.get("starts_ms"),
                        body.get("operator_id"),body.get("approval_id"),
                        body.get("locked_original_runtime_source_sha"))
    require(body==expected and body["lane"]==lane,
            "operator grant not scoped to exact source, lane or time")
    require(body["starts_ms"]<=now_ms<body["expires_ms"],
            "operator grant not yet effective or expired")
    return body

def secure_posix_key(path):
    """Production activation intentionally refused without real POSIX custody."""
    require(os.name=="posix","installed Windows protected key custody unqualified")
    path=Path(path)
    st=path.lstat()
    require(stat.S_ISREG(st.st_mode) and st.st_uid==os.getuid()
            and stat.S_IMODE(st.st_mode)==0o600 and st.st_nlink==1,
            "operator key file must be owned regular 0600 POSIX file")
    key=path.read_bytes()
    require(len(key)==32,"operator key must be exactly 32 random bytes")
    return key

class Journal:
    def __init__(self,path,lane,approved_body):
        require(lane in p.LANES,"unknown original independent source lane")
        self.path=Path(path);self.lane=lane
        self.grant_id=digest(approved_body)
        require(self.path.parent.exists(),"durable journal parent must pre-exist")
        if os.name=="posix":
            mode=stat.S_IMODE(self.path.parent.stat().st_mode)
            require(mode & 0o077==0,"operator journal directory permissions too open")
        self.db=sqlite3.connect(str(self.path),timeout=5,isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        self.db.execute("""CREATE TABLE IF NOT EXISTS events (
            number INTEGER PRIMARY KEY,slot INTEGER NOT NULL,
            kind TEXT NOT NULL,prior_sha256 TEXT NOT NULL,
            event_sha256 TEXT NOT NULL,record TEXT NOT NULL)""")
        for op in ("UPDATE","DELETE"):
            self.db.execute(f"""CREATE TRIGGER IF NOT EXISTS immutable_events_{op.lower()}
                BEFORE {op} ON events BEGIN SELECT RAISE(ABORT,'immutable source journal'); END""")
        values=dict(self.db.execute("SELECT key,value FROM meta").fetchall())
        expected={"schema":SCHEMA,"lane":lane,"grant_identity_sha256":self.grant_id}
        if values:
            require(values==expected,"reopened journal uses different approval or lane")
        else:
            self.db.executemany("INSERT INTO meta VALUES(?,?)",list(expected.items()))
        self.verify_chain()

    def close(self):self.db.close()

    def events(self):
        return [json.loads(row[0]) for row in self.db.execute(
            "SELECT record FROM events ORDER BY number")]

    def verify_chain(self):
        previous=p.GENESIS
        result=self.events()
        for i,record in enumerate(result):
            require(record["schema"]==SCHEMA
              and record["number"]==i
              and record["lane"]==self.lane
              and record["grant_identity_sha256"]==self.grant_id
              and record["prior_sha256"]==previous,
              "durable journal missing, reordered or mismatched event")
            signature=record["event_sha256"]
            require(signature==digest({k:v for k,v in record.items()
                                      if k!="event_sha256"}),
                    "durable journal event changed after original source capture")
            previous=signature
        require(len(result)==self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                "journal rows unexpectedly missing")
        return result

    def append(self,events):
        """One source event batch committed atomically under SQLite writer lock."""
        require(type(events) is list and bool(events),"no source journal event")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            last=self.db.execute(
                "SELECT number,event_sha256 FROM events ORDER BY number DESC LIMIT 1").fetchone()
            index=(last[0]+1) if last else 0
            previous=last[1] if last else p.GENESIS
            new=[]
            for event in events:
                require(event["kind"] in ("INTENT","OBSERVED","ERROR","GAP","INTERRUPTED")
                   and type(event["slot"]) is int and 0<=event["slot"]<MAX_SLOTS,
                   "invalid bounded original poll event")
                row={"schema":SCHEMA,"number":index,"lane":self.lane,
                     "grant_identity_sha256":self.grant_id,"slot":event["slot"],
                     "kind":event["kind"],"prior_sha256":previous,
                     "payload":event["payload"]}
                row["event_sha256"]=digest(row)
                self.db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)",(
                    index,row["slot"],row["kind"],previous,
                    row["event_sha256"],canonical(row).decode()))
                new.append(row);index+=1;previous=row["event_sha256"]
            self.db.execute("COMMIT")
            return new
        except:
            self.db.execute("ROLLBACK")
            raise

    def slot_events(self,slot):
        self.verify_chain()
        return [e for e in self.events() if e["slot"]==slot]

    def export_slot(self,slot):
        rows=self.slot_events(slot)
        require(rows and (
            len(rows)==1 and rows[0]["kind"]=="GAP" or
            len(rows)==2 and rows[0]["kind"]=="INTENT" and
              rows[1]["kind"] in ("OBSERVED","ERROR","INTERRUPTED")),
            "cannot publish incomplete or malformed source slot")
        return {"schema":"cognitum.orc.bench02.r5.prospective01.slot.v1",
            "lane":self.lane,"slot":slot,"grant_identity_sha256":self.grant_id,
            "prior_head_sha256":rows[0]["prior_sha256"],
            "terminal_head_sha256":rows[-1]["event_sha256"],
            "events":rows,"external_GitHub_artifact_not_yet_proven":True}

def terminal_for_slot(events,slot):
    found=[r for r in events if r["slot"]==slot]
    if not found:return None
    end=found[-1]["kind"]
    return end if end in ("OBSERVED","ERROR","GAP","INTERRUPTED") else None

def recover_orphan(journal,now_ms):
    events=journal.verify_chain()
    if events and events[-1]["kind"]=="INTENT":
        last=events[-1]
        journal.append([{"slot":last["slot"],"kind":"INTERRUPTED",
                        "payload":{"reason":"crashed_or_terminated_after_durable_INTENT",
                        "recovered_at_ms_untrusted":now_ms,
                        "original_http_result_was_not_durably_saved":True}}])

def request_once(journal,grant,key,now_ms,fetcher):
    """Never retries an attempted slot. No wait loop or network by default."""
    body=check_grant(grant,key,journal.lane,now_ms)
    journal.verify_chain()
    recover_orphan(journal,now_ms)
    slot=(now_ms-body["starts_ms"])//PERIOD
    require(0<=slot<MAX_SLOTS,"not an approved source polling slot")
    prior=journal.events()
    previous_slots=[r["slot"] for r in prior if r["kind"] in ("GAP","INTENT")]
    last_slot=max(previous_slots) if previous_slots else -1
    require(slot>last_slot,"original NOAA poll slot already attempted or clock rolled back")
    missed=[]
    for s in range(last_slot+1,slot):
        missed.append({"slot":s,"kind":"GAP",
            "payload":{"scheduled_start_ms":body["starts_ms"]+s*PERIOD,
              "discovered_at_ms_untrusted":now_ms,
              "reason":"no_qualifying_source_request_in_precommitted_slot",
              "source_observed":False}})
    if missed:journal.append(missed)
    slot_start=body["starts_ms"]+slot*PERIOD
    if now_ms-slot_start>MAX_DELAY:
        journal.append([{"slot":slot,"kind":"GAP",
            "payload":{"scheduled_start_ms":slot_start,
             "discovered_at_ms_untrusted":now_ms,
             "reason":"timer_or_runner_late_beyond_2_minutes","source_observed":False}}])
        return "GAP"
    journal.append([{"slot":slot,"kind":"INTENT",
        "payload":{"scheduled_start_ms":slot_start,
            "started_ms_untrusted":now_ms,"url":p.URL,
            "no_automatic_retry":True}}])
    try:
        status,ctype,raw,http_date=fetcher()
        end=int(time.time_ns()//1_000_000)
        require(type(raw) is bytes and len(raw)<=MAX_RESPONSE,
                "original NOAA response exceeded source limit")
        if status==200:
            try:
                original=p.new_capture(raw,lane=journal.lane,seq=slot,
                    prev=p.GENESIS,started=now_ms,ended=max(now_ms,end),
                    status=status,content_type=ctype,http_date=http_date)
                record={"capture":original}
                kind="OBSERVED"
            except (p.Refusal,ValueError):
                kind="ERROR";record={"reason":"malformed_or_ambiguous_HTTP_200",
                     "status":status,"body_sha256":sha256(raw).hexdigest(),
                     "body_original_base64":b64encode(raw).decode(),
                     "content_type":ctype}
        else:
            kind="ERROR";record={"reason":"HTTP_NON_200",
                "status":status,"body_sha256":sha256(raw).hexdigest(),
                "body_original_base64":b64encode(raw).decode(),
                "content_type":ctype}
    except (URLError,OSError,TimeoutError):
        kind="ERROR";record={"reason":"network_error_no_original_source",
                             "status":None,"body_sha256":None}
    except (TypeError,Refusal,ValueError):
        kind="ERROR";record={"reason":"invalid_or_oversized_original_provider_response",
                             "status":None,"body_sha256":None}
    journal.append([{"slot":slot,"kind":kind,"payload":record}])
    return kind

def bounded_original_noaa_get():
    q=policy()
    req=Request(p.URL,headers={"User-Agent":p.prereg()["prospective_data"]["http_user_agent"],
                               "Accept":"application/json"})
    try:
        with urlopen(req,timeout=15) as response:
            return response.status,response.headers.get("Content-Type",""),\
                response.read(MAX_RESPONSE+1),response.headers.get("Date","")
    except HTTPError as ex:
        return ex.code,ex.headers.get("Content-Type",""),ex.read(MAX_RESPONSE+1),\
               ex.headers.get("Date","")

def operator_once(*,lane,grant_path,key_path,journal_path):
    """Explicit one-shot source capture; scheduler is external and not installed."""
    key=secure_posix_key(key_path)
    approved=json.loads(Path(grant_path).read_bytes())
    now=int(time.time_ns()//1_000_000)
    body=check_grant(approved,key,lane,now)
    j=Journal(journal_path,lane,body)
    try:
        result=request_once(j,approved,key,now,bounded_original_noaa_get)
        # No successful observation is called externally anchored yet.
        print(json.dumps({"lane":lane,"result":result,
            "last_journal_head":j.events()[-1]["event_sha256"],
            "source_first_seen_externally_verified":False}))
        return result
    finally:j.close()


def cli(argv=None):
    """Explicit one-shot operator entrypoint, no daemon, no key generation."""
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--lane",choices=p.LANES,required=True)
    parser.add_argument("--grant",required=True)
    parser.add_argument("--key-file",required=True)
    parser.add_argument("--journal",required=True)
    parser.add_argument("--export-slot",type=int,default=None)
    parser.add_argument("--export-output",default=None)
    args=parser.parse_args(argv)
    if args.export_slot is None:
        require(args.export_output is None,"archive output requires exact slot")
        operator_once(lane=args.lane,grant_path=args.grant,
                     key_path=args.key_file,journal_path=args.journal)
    else:
        require(args.export_output and args.export_slot>=0,
                "one exact original poll slot export destination required")
        key=secure_posix_key(args.key_file)
        grant=json.loads(Path(args.grant).read_bytes())
        body=check_grant(grant,key,args.lane,int(time.time_ns()//1_000_000))
        j=Journal(args.journal,args.lane,body)
        try:
            result=j.export_slot(args.export_slot)
            with Path(args.export_output).open("x",encoding="utf-8",newline="\n") as f:
                json.dump(result,f,sort_keys=True,indent=2)
                f.write("\n")
            print(json.dumps({"slot":args.export_slot,
                "journal_terminal_sha256":result["terminal_head_sha256"],
                "trusted_external_GitHub_artifact_yet_verified":False}))
        finally:j.close()

if __name__=="__main__":
    cli()
