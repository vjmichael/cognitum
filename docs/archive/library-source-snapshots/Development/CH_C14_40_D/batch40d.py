"""CH40-D scoped fresh local proof witnesses over all 15 original frozen cases.

Every witness is emitted by CH40-B producer code, then validated using the
separate CH40-D rational/Decimal directed mathematical kernel. These are NEW
finite-box certificates. Historical 160-bit/224-bit producer caps are not
silently certified. No original signed CH39 attestor ledger is modified.
"""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,json,os,pathlib,sys,time,traceback,zipfile
from verify_original40 import decode_case,ORIGINAL_ZIP_SHA256
from witness_producer40d import direct_witness,coupled_witness,taylor_witness,newton_witness
from witness_checker40d import verify,digest

ROOT=pathlib.Path(__file__).resolve().parent
ARCHIVE_NAME='Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'

def audit_one(args):
    archive,case,pin,out=args;t=time.monotonic()
    with zipfile.ZipFile(archive) as z:cert=decode_case(z,case,{case:pin})
    coupled=next((n['id'] for n in cert['nodes'] if n['upper_method']=='coupled_logdet_dual'),None)
    if coupled is None:raise AssertionError('Frozen proof has no coupled producer rule')
    makers={'DIRECT':lambda:direct_witness(cert,0),
            'COUPLED_TANGENT':lambda:coupled_witness(cert,coupled),
            'TAYLOR2':lambda:taylor_witness(cert,0),
            'KRAWCZYK':lambda:newton_witness(cert,0)}
    witnesses={};receipts={}
    for kind,producer in makers.items():
        witness=producer();receipt=verify(cert,witness)
        if not receipt['valid_local_witness'] or receipt['global_optimality_certified'] or receipt['scientific_release']!='NO_GO':raise AssertionError('Invalid scope')
        witnesses[kind]=witness;receipts[kind]=receipt
    result={'case':case,'status':'PASS_LOCAL_FINITE_WITNESS_ONLY','source_archive_sha256':ORIGINAL_ZIP_SHA256,
            'source_certificate_sha256':digest(cert),'witnesses':witnesses,'receipts':receipts,
            'newtons_status':witnesses['KRAWCZYK']['claim']['status'],'seconds':round(time.monotonic()-t,3),
            'certifies_archived_producer_caps':False,'scientific_release':'NO_GO'}
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    dst=out/(case+'.json');tmp=dst.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');os.replace(tmp,dst)
    return {'case':case,'status':'PASS','newton':result['newtons_status'],'seconds':result['seconds'],
            'file_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),
            'coupled_source_node':coupled,'witness_types':list(witnesses)}

def execute(archive,out,cases=None,jobs=3):
    archive=pathlib.Path(archive);out=pathlib.Path(out)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=ORIGINAL_ZIP_SHA256:raise ValueError('Original CH39 archive pin mismatch')
    with zipfile.ZipFile(archive) as z:pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
    targets=sorted(pins) if not cases else cases
    if len(set(targets))!=len(targets) or any(c not in pins for c in targets):raise ValueError('Unknown/repeated frozen case')
    results={};out.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1,min(jobs,4))) as executor:
        futs={executor.submit(audit_one,(str(archive),c,pins[c],str(out))):c for c in targets}
        for f in concurrent.futures.as_completed(futs):
            c=futs[f]
            try:rec=f.result()
            except Exception as e:rec={'case':c,'status':'FAIL','message':repr(e),'trace':traceback.format_exc(limit=3)}
            results[c]=rec
            print(rec['status'],c,rec.get('newton',rec.get('message')),'elapsed',rec.get('seconds','?'),flush=True)
            summ={'version':'CH40D-LOCAL-WITNESS-V1','source_zip_sha256':ORIGINAL_ZIP_SHA256,
                  'requested_cases':len(targets),'completed':len(results),'cases':results,
                  'passed':sum(r['status']=='PASS' for r in results.values()),'failed':sum(r['status']=='FAIL' for r in results.values()),
                  'historical_producer_caps_certified':False,'scientific_release':'NO_GO','no_global_optimality':True}
            fp=out/'CH40D_SUMMARY.json';tmp=fp.with_suffix('.tmp')
            tmp.write_text(json.dumps(summ,indent=2,sort_keys=True)+'\n');os.replace(tmp,fp)
    return int(len(results)!=len(targets) or any(r['status']!='PASS' for r in results.values()))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=pathlib.Path,default=ROOT/ARCHIVE_NAME)
    p.add_argument('--out',type=pathlib.Path,default=ROOT/'CH40D_RESULTS')
    p.add_argument('--case',action='append',default=None);p.add_argument('--jobs',type=int,default=3)
    a=p.parse_args();raise SystemExit(execute(a.archive,a.out,a.case,a.jobs))