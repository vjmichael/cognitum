"""CH40-A bounded, checkpointed independent Decimal mathematical verification batch.

Runs each of the 15 sealed original CH23 certificates through the separate
mathematical implementation; resume only when source and original archive
hashes match. Results written atomically after EACH completed case.
"""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,json,os,pathlib,sys,time,uuid,zipfile
from verify_original40 import decode_case,ORIGINAL_ZIP_SHA256
from independent_checker40 import verify_certificate

D=pathlib.Path(__file__).resolve().parent
SOURCE_NAMES=['exact_decimal40.py','independent_checker40.py','verify_original40.py','batch40.py']

def fingerprint():
 h=hashlib.sha256()
 for f in SOURCE_NAMES:
  data=(D/f).read_bytes();h.update(f.encode()+b'\0'+hashlib.sha256(data).digest())
 return h.hexdigest()

def _run_one(archive,case):
 t=time.perf_counter()
 with zipfile.ZipFile(archive) as z:
  pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
  cert=decode_case(z,case,pins)
  result=verify_certificate(cert)
 return case, {'case_id':case,'status':'PASS_INDEPENDENT_REPLAY_UNRESOLVED' if not result['bounded_gap_proven_by_independent_checker'] else 'REVIEW_REQUIRED',
               'elapsed_seconds':round(time.perf_counter()-t,3),'result':result}

def atomic_json(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.pending')
 try:
  with open(tmp,'x',encoding='utf8') as fp:
   json.dump(obj,fp,indent=2,sort_keys=True);fp.write('\n');fp.flush();os.fsync(fp.fileno())
  os.replace(tmp,path)
 finally:
  if tmp.exists():tmp.unlink()

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('archive',type=pathlib.Path)
 ap.add_argument('--out',type=pathlib.Path,default=D/'CH40A_original15_results.json')
 ap.add_argument('--workers',type=int,default=3)
 a=ap.parse_args()
 if not (1<=a.workers<=4):raise ValueError('At most four bounded verifier workers')
 if hashlib.sha256(a.archive.read_bytes()).hexdigest()!=ORIGINAL_ZIP_SHA256:raise ValueError('Original archive hash mismatch')
 with zipfile.ZipFile(a.archive) as z:
  pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
  caseids=sorted(pins)
 proof={'version':'CH40-A','archive_sha256':ORIGINAL_ZIP_SHA256,'code_fingerprint':fingerprint(),
        'status':'IN_PROGRESS','results':{},'scientific_release':'NO_GO','scope':'independent finite coefficient-box replay; not full R^d or producer-bound equivalence'}
 if a.out.exists():
  old=json.loads(a.out.read_text())
  if old['archive_sha256']!=proof['archive_sha256'] or old['code_fingerprint']!=proof['code_fingerprint']:
   raise ValueError('Cannot resume across a different original archive/code fingerprint')
  proof['results']=old['results']
 pending=[x for x in caseids if x not in proof['results']]
 print('CH40-A',len(pending),'pending from',len(caseids),'original cases; verified resume',len(proof['results']),flush=True)
 if pending:
  with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
   jobs={pool.submit(_run_one,a.archive,case):case for case in pending}
   for f in concurrent.futures.as_completed(jobs):
    case=jobs[f]
    try:k,v=f.result()
    except BaseException as exc:
     proof['results'][case]={'case_id':case,'status':'FAIL','error_type':type(exc).__name__,'reason':str(exc)[:500]}
    else:proof['results'][k]=v
    atomic_json(a.out,proof)
    print('CH40-A',len(proof['results']),'/',len(caseids),case,proof['results'][case]['status'],flush=True)
 counts={k:sum(x['status']==k for x in proof['results'].values()) for k in set(x['status'] for x in proof['results'].values())}
 proof['counts']=counts
 proof['status']='PASS_INDEPENDENT_REPLAY_ALL_UNRESOLVED' if len(proof['results'])==len(caseids) and counts.get('PASS_INDEPENDENT_REPLAY_UNRESOLVED')==len(caseids) else 'INCOMPLETE_OR_REVIEW_REQUIRED'
 atomic_json(a.out,proof)
 print(proof['status'],counts,flush=True)
 return 0 if proof['status'].startswith('PASS') else 1
if __name__=='__main__':raise SystemExit(main())