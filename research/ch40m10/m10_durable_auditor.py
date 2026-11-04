"""CH40-M.10 trusted-verifier attestation + durable case-level recovery.

Research only; this does NOT independently validate global C14 optimality.
First acceptance invokes unmodified M8 independent rational replay. Recovery
accepts that prior result ONLY when the trusted verifier signature, original
source pins, current input journals and ordered checkpoint ledger match.

Trust prerequisite: the externally pinned verifier Ed25519 public key is
trusted and signing private key remains outside the producer's control.
With same-UID malicious code capable of stealing that key, this boundary is
NOT secure. A fully user-writable state directory cannot prevent rollback of
valid final rows without an out-of-band monotonic anchor.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import time
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('CH40M10_WORKSPACE','/mnt/data')).resolve()
sys.path.insert(0,str(ROOT/'CH40M8'))
from audit_m8 import run_batch, _load_pins, _prepare_original

PROTOCOL='CH40M10-TRUSTED-VERIFIER-DURABLE-CHECKPOINT-V1'
RULE='PSD_GRAM_DOMINANCE'
ENGINES=('arb_gram','mpfr_gram')
CASE_ORDER=('quasi_separated_n80_i00','quasi_separated_n160_i00',
 'zero_balanced_n80_i00','zero_balanced_n160_i00',
 'one_event_n80_i00','one_event_n160_i00',
 'zero_imbalanced_n80_i00','zero_imbalanced_n160_i00',
 'rare_1pct_n80_i00','rare_1pct_n160_i00',
 'rare_5pct_n80_i00','rare_5pct_n160_i00',
 'zero_imbalanced_n160_i05','zero_imbalanced_n160_i07',
 'rare_1pct_n160_i13')
class Refusal(RuntimeError):pass

def canonical(obj:Any)->bytes:
    return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')

def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def file_sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def load_public(path:Path)->tuple[Ed25519PublicKey,str]:
    raw=Path(path).read_bytes()
    if len(raw)!=32:raise Refusal('bad trusted public key length')
    try:return Ed25519PublicKey.from_public_bytes(raw),digest(raw)
    except ValueError as e:raise Refusal('invalid trusted public key') from e

def load_private(path:Path)->Ed25519PrivateKey:
    p=Path(path)
    if os.name=='posix' and p.stat().st_mode & 0o077:
        raise Refusal('signer private key must be owner-only (chmod 600)')
    raw=p.read_bytes()
    if len(raw)!=32:raise Refusal('bad verifier signing key length')
    return Ed25519PrivateKey.from_private_bytes(raw)

def make_keys(key_dir:Path):
    key_dir=Path(key_dir)
    key_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    secret=key_dir/'verifier-private.key';public=key_dir/'verifier-public.key'
    if secret.exists() or public.exists():raise Refusal('refusing to overwrite existing key')
    signer=Ed25519PrivateKey.generate()
    raw=signer.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption())
    fd=os.open(secret,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    public.write_bytes(signer.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw))
    return public,secret

CHECKER_FILES=(
 'CH40M8/audit_m8.py',
 'CH40M5/independent_psd_check.py',
 'CH40L2/continue40l2.py',
 'CH40L/analyze40l.py',
 'CH40J/source/rational_kernel40d.py',
)

def source_code_pins()->dict:
    pins={}
    for rel in CHECKER_FILES:
        path=ROOT/rel
        if not path.is_file():raise Refusal('trusted independent verifier source missing: '+rel)
        pins[rel]=file_sha(path)
    return pins

def manifest(cases,source_root:Path,public_fingerprint:str):
    if not cases or len(cases)!=len(set(cases)) or any(c not in CASE_ORDER for c in cases):
        raise Refusal('case list contains duplicates or non-original case')
    pins=_load_pins()
    if len(pins)!=15:raise Refusal('original 15-case pinset is incomplete')
    p=source_root/'CH40K/CH40K_ACCEPTANCE.json'
    if p.resolve()!=(ROOT/'CH40K/CH40K_ACCEPTANCE.json').resolve():
        raise Refusal('source workspace differs from M8 independent audit workspace')
    return {'protocol':PROTOCOL,'formula':RULE,'scientific_release':'NO_GO',
            'pinset_sha256':file_sha(p),'case_order':list(cases),
            'trusted_verifier_public_sha256':public_fingerprint,
            'trusted_checker_source_pins':source_code_pins()}

def pinned_original_hash(case:str,pins:dict)->str:
    entry=pins.get(case)
    if not isinstance(entry,dict) or type(entry.get('trace_sha256')) is not str:
        raise Refusal('missing original case trace pin')
    original=ROOT/'CH40K/traces'/(case+'_127_original_mpfr_trace.json')
    if not original.is_file():raise Refusal('original trace absent')
    actual=file_sha(original)
    if actual!=entry['trace_sha256']:raise Refusal('original trace SHA mismatch on resume')
    return actual

def journal_hashes(inputs:Path,case:str):
    result={}
    for engine in ENGINES:
        p=inputs/(case+'_'+engine+'.json')
        if not p.is_file():raise Refusal('missing original search journal: '+p.name)
        result[engine]=file_sha(p)
    return result

def checkpoint_body(prev:str,index:int,case:str,trace_sha:str,hashes:dict,receipt:dict):
    return {'protocol':PROTOCOL,'sequence':index+1,'case':case,
            'original_trace_sha256':trace_sha,'journal_sha256':hashes,
            'prev_tip':prev,'audited_receipt':receipt,'scientific_release':'NO_GO'}

def receipt_check(receipt:dict,case:str,trace_sha:str,hashes:dict):
    if (receipt.get('protocol')!='CH40M8-EXACT-KEY-INPROCESS-INDEPENDENT-RATIONAL-AUDIT-V1' or
        receipt.get('mode')!='cache' or receipt.get('status')!='PASS_RESEARCH_ONLY' or
        receipt.get('scientific_release')!='NO_GO' or receipt.get('cases')!=1 or
        receipt.get('input_count')!=2):
        raise Refusal('invalid independently audited receipt status/coverage')
    recs=receipt.get('receipts')
    if not isinstance(recs,list) or len(recs)!=2 or {r.get('backend') for r in recs}!=set(ENGINES):
        raise Refusal('missing required paired independent audit receipts')
    checked=0;ids=[]
    for r in recs:
        if (r.get('case')!=case or r.get('original_trace_sha256')!=trace_sha or
            r.get('journal_file')!=case+'_'+r.get('backend','')+'.json' or
            r.get('journal_sha256')!=hashes[r['backend']] or
            r.get('status')!='PASS_INDEPENDENT_RATIONAL_BATCH_REPLAY' or
            type(r.get('children_checked')) is not int or r['children_checked']<0 or
            type(r.get('checked_proposition_ids')) is not list or
            len(r['checked_proposition_ids'])!=r['children_checked']):
            raise Refusal('receipt source, journal or proof identity mismatch')
        checked+=r['children_checked'];ids.extend(r['checked_proposition_ids'])
    props=receipt.get('propositions')
    if not isinstance(props,list) or not all(isinstance(p,dict) for p in props):
        raise Refusal('invalid proposition ledger')
    for p in props:
        if p.get('original_trace_sha256')!=trace_sha or p.get('formula')!=RULE:
            raise Refusal('unfrozen or wrong-rule proof proposition')
        statement={k:p[k] for k in ('original_trace_sha256','formula','exact_box','independent_upper')}
        if digest(canonical(statement))!=p.get('proof_id'):
            raise Refusal('altered proof proposition')
    if len({p['proof_id'] for p in props}) != len(props):
        raise Refusal('duplicate independent proof proposition')
    if (receipt.get('children_checked')!=checked or
        receipt.get('independent_rational_computations')!=len(props) or
        receipt.get('same_box_cache_hits')!=checked-len(props) or
        receipt.get('proposition_ledger_sha256')!=digest(canonical(props)) or
        receipt.get('archive_sha256')!=digest(canonical(recs)) or
        not set(ids)<= {p['proof_id'] for p in props}):
        raise Refusal('altered coverage or independent-ledger commitment')
    return checked

def open_db(db_path:Path):
    db_path=Path(db_path)
    db_path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(str(db_path),isolation_level=None,timeout=2)
    conn.execute('PRAGMA journal_mode=DELETE')
    conn.execute('PRAGMA synchronous=FULL')
    conn.execute('PRAGMA busy_timeout=2000')
    conn.execute('CREATE TABLE IF NOT EXISTS meta (id INTEGER PRIMARY KEY CHECK(id=1), manifest BLOB NOT NULL, genesis TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS verified (idx INTEGER PRIMARY KEY, case_name TEXT NOT NULL UNIQUE, body BLOB NOT NULL, body_sha TEXT NOT NULL, signature BLOB NOT NULL, tip TEXT NOT NULL)')
    return conn

def init_or_check(conn,expected:dict):
    b=canonical(expected);genesis=digest(b'CH40M10-GENESIS\0'+b)
    row=conn.execute('SELECT manifest,genesis FROM meta WHERE id=1').fetchone()
    if row:
        if row[0]!=b or row[1]!=genesis:raise Refusal('immutable run manifest or trusted signer changed')
    else:
        if conn.execute('SELECT COUNT(*) FROM verified').fetchone()[0]:
            raise Refusal('unbound recovered rows without a genesis manifest')
        with conn:conn.execute('INSERT INTO meta(id,manifest,genesis) VALUES (1,?,?)',(b,genesis))
    return genesis

def verify_rows(conn,inputs:Path,cases,public:Ed25519PublicKey,genesis:str,pins:dict):
    rows=conn.execute('SELECT idx,case_name,body,body_sha,signature,tip FROM verified ORDER BY idx').fetchall()
    if len(rows)>len(cases):raise Refusal('checkpoint count exceeds run manifest')
    prev=genesis;child_total=0;read_hashes=[]
    for index,row in enumerate(rows):
        idx,case,blob,h,sig,tip=row
        if idx!=index or case!=cases[index]:raise Refusal('deleted, reordered, duplicated checkpoint')
        if digest(blob)!=h:raise Refusal('altered checkpoint contents')
        try:public.verify(sig,b'CH40M10-VERIFIER\0'+blob)
        except InvalidSignature as e:raise Refusal('forged or wrong-key checkpoint signature') from e
        try:body=json.loads(blob)
        except (json.JSONDecodeError,UnicodeDecodeError) as e:raise Refusal('checkpoint JSON invalid') from e
        if (canonical(body)!=blob or body.get('sequence')!=index+1 or body.get('case')!=case or
            body.get('prev_tip')!=prev or body.get('protocol')!=PROTOCOL or
            body.get('scientific_release')!='NO_GO'):
            raise Refusal('noncanonical, out-of-order or spliced checkpoint')
        # Rehash immutable original trace (validated against certificate and SHA
        # by the independent M8 verifier when this signature was issued). No
        # expensive reparse/re-execution of mathematics is needed on restart.
        trace_sha=pinned_original_hash(case,pins)
        if body.get('original_trace_sha256')!=trace_sha:raise Refusal('changed original evidence')
        hashes=journal_hashes(inputs,case)
        if body.get('journal_sha256')!=hashes:raise Refusal('journal changed since trusted verification')
        child_total+=receipt_check(body['audited_receipt'],case,trace_sha,hashes)
        expected_tip=digest(canonical({'previous':prev,'body_sha256':h,'signature':base64.b64encode(sig).decode('ascii')}))
        if expected_tip!=tip:raise Refusal('checkpoint chain broken')
        prev=tip;read_hashes.append(h)
    return {'completed':len(rows),'children_checked':child_total,'tip':prev,'body_hashes':read_hashes}

def accepted_case(conn,case,index,prev,trace_sha,hashes,receipt,signer):
    receipt_check(receipt,case,trace_sha,hashes)
    body=checkpoint_body(prev,index,case,trace_sha,hashes,receipt)
    blob=canonical(body);sig=signer.sign(b'CH40M10-VERIFIER\0'+blob)
    hh=digest(blob)
    tip=digest(canonical({'previous':prev,'body_sha256':hh,'signature':base64.b64encode(sig).decode('ascii')}))
    conn.execute('BEGIN IMMEDIATE')
    try:
        # A split verification either publishes its full authenticated receipt or nothing.
        conn.execute('INSERT INTO verified(idx,case_name,body,body_sha,signature,tip) VALUES (?,?,?,?,?,?)',
                     (index,case,blob,hh,sig,tip))
        conn.execute('COMMIT')
    except BaseException:
        try:conn.execute('ROLLBACK')
        except sqlite3.Error:pass
        raise
    return tip

def run(db_path:Path,inputs:Path,cases:list[str],public_path:Path,secret_path:Path|None=None,stop_after:int|None=None,kill_after:int|None=None,expected_tip:str|None=None):
    started=time.process_time()
    pub,fp=load_public(public_path)
    signer=load_private(secret_path) if secret_path else None
    if signer and signer.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)!=Path(public_path).read_bytes():
        raise Refusal('private signer does not match externally pinned trusted key')
    man=manifest(cases,ROOT,fp);pins=_load_pins()
    db=Path(db_path).resolve();inputs=Path(inputs).resolve()
    if db.parent==Path(public_path).resolve().parent:
        raise Refusal('checkpoint database and trusted public key must not share directory')
    conn=open_db(db)
    try:
        genesis=init_or_check(conn,man)
        state=verify_rows(conn,inputs,cases,pub,genesis,pins)
        if expected_tip is not None and state['tip']!=expected_tip:
            raise Refusal('checkpoint rollback or wrong external expected tip')
        reused=state['completed'];new=0;tip=state['tip']
        print(f'RECOVERED signed_cases={reused} signed_children={state["children_checked"]}',flush=True)
        for idx in range(reused,len(cases)):
            if stop_after is not None and new>=stop_after:break
            if signer is None:raise Refusal('no trusted verifier signer for new verification')
            case=cases[idx]
            _,_,trace_sha=_prepare_original(case,pins)
            hashes=journal_hashes(inputs,case)
            outcome=run_batch(inputs,mode='cache',cases=[case])
            tip=accepted_case(conn,case,idx,tip,trace_sha,hashes,outcome,signer)
            new+=1
            print(f'COMMITTED {idx+1}/{len(cases)} {case} children={outcome["children_checked"]} tip={tip[:12]}',flush=True)
            if kill_after is not None and new==kill_after:
                print('INJECTING_REAL_SIGKILL_AFTER_COMMIT',flush=True)
                os.kill(os.getpid(),signal.SIGKILL)
        final=verify_rows(conn,inputs,cases,pub,genesis,pins)
        total=time.process_time()-started
        return {'protocol':PROTOCOL,'status':'PARTIAL_RESEARCH_ONLY' if final['completed']<len(cases) else 'ACCEPTED_RESEARCH_ONLY',
                'scientific_release':'NO_GO','original_cases_requested':len(cases),
                'cases_reused_after_signature_and_input_checks':reused,'cases_newly_independently_audited':new,
                'completed_cases':final['completed'],'verified_child_checks':final['children_checked'],
                'terminal_checkpoint_tip':final['tip'],'full_process_cpu_seconds':total,
                'trust_model':('Externally pinned verifier Ed25519 public key, original trace/journal/source code hashes. '
                 'Previous tip independently pinned.' if expected_tip else
                 'Externally pinned verifier Ed25519 public key, original trace/journal/source code hashes. '
                 'No out-of-band antirollback anchor supplied.')}
    finally:conn.close()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--db',type=Path)
    p.add_argument('--inputs',type=Path,default=ROOT/'CH40M9/full15/journals')
    p.add_argument('--public',type=Path)
    p.add_argument('--private',type=Path)
    p.add_argument('--cases',nargs='+',default=list(CASE_ORDER))
    p.add_argument('--stop-after',type=int)
    p.add_argument('--kill-after-commit',type=int)
    p.add_argument('--expected-tip',help='Externally pinned previous tip (reject rollback)')
    p.add_argument('--create-keys',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    try:
        if a.create_keys:
            pub,sec=make_keys(a.create_keys)
            print(json.dumps({'public':str(pub),'private':str(sec),'public_sha256':file_sha(pub)}))
            return
        if not a.db or not a.public:raise Refusal('required --db and --public')
        result=run(a.db,a.inputs,a.cases,a.public,a.private,a.stop_after,a.kill_after_commit,a.expected_tip)
        if a.output:
            a.output.parent.mkdir(parents=True,exist_ok=True)
            temp=a.output.with_name(a.output.name+'.tmp')
            with temp.open('w') as f:
                json.dump(result,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
            os.replace(temp,a.output)
        print('RESULT',json.dumps(result,sort_keys=True),flush=True)
    except (Refusal,sqlite3.Error,OSError,KeyError,ValueError) as e:
        print('REFUSED',type(e).__name__,str(e),file=sys.stderr,flush=True)
        sys.exit(2)
if __name__=='__main__':main()
