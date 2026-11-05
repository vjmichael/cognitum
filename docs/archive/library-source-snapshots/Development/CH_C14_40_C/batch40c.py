"""Full frozen CH40-C independent producer-rule replay with atomic per-case output.

Outcome is research consistency, not producer cap certification. Each case
independently replays 127 nodes and records which displayed cap claims have
independent justification; unverified display numbers remain untrusted.
"""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,json,os,pathlib,time,zipfile
from verify_original40 import ORIGINAL_ZIP_SHA256,decode_case
from rule_checker40c import verify_tree
from independent_checker40 import canonical

HERE=pathlib.Path(__file__).resolve().parent

def check_one(args):
    archive,case=args
    with zipfile.ZipFile(archive) as z:
        pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
        cert=decode_case(z,case,pins)
    result=verify_tree(cert)
    return result

def write_atomic(dest,data):
    dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix(dest.suffix+'.tmp')
    with tmp.open('wb') as f:
        f.write(canonical(data));f.flush();os.fsync(f.fileno())
    os.replace(tmp,dest)

def run(archive,out,cases=None,jobs=4):
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=ORIGINAL_ZIP_SHA256:raise ValueError('Untrusted sealed source ZIP')
    with zipfile.ZipFile(archive) as z:pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
    targets=list(cases or sorted(pins))
    if len(set(targets))!=len(targets) or any(x not in pins for x in targets):raise ValueError('Unknown or duplicate case')
    # Always recompute mathematics; unsigned cached JSON cannot be trusted.
    # Per-case files are diagnostic recovery artifacts, NOT authority.
    results={}
    tasks=[(str(archive),case) for case in targets]
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1,min(jobs,4))) as pool:
        fs={pool.submit(check_one,pair):pair[1] for pair in tasks}
        for future in concurrent.futures.as_completed(fs):
            case=fs[future]
            try:
                v=future.result()
                if v['nodes_replayed']!=127 or v['independent_finite_gap_proven']:
                    raise ValueError('No automatic scientific or partial promotion')
                results[case]=v;write_atomic(out/(case+'.json'),v)
                print('PASS',case, v['stats'],flush=True)
            except Exception as e:
                results[case]={'status':'FAIL','case':case,'error':repr(e)}
                print('FAIL',case,repr(e),flush=True)
    summary={'protocol':'CH40C-RESEARCH-V1','source_sha256':ORIGINAL_ZIP_SHA256,
      'passed':sum(x.get('nodes_replayed')==127 for x in results.values()),
      'failed':sum(x.get('status')=='FAIL' for x in results.values()),
      'total':len(targets),'nodes_verified':sum(x.get('nodes_replayed',0) for x in results.values()),
      'producer_local_displays_justified':sum(x.get('stats',{}).get('producer_local_displays_justified',0) for x in results.values()),
      'producer_inherited_displays_justified':sum(x.get('stats',{}).get('producer_inherited_displays_justified',0) for x in results.values()),
      'producer_fully_certified':False,'scientific_release':'NO_GO'}
    write_atomic(out/'CH40C_SUMMARY.json',summary)
    print(json.dumps(summary,indent=2),flush=True)
    return summary

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--archive',type=pathlib.Path,default=HERE/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip');a.add_argument('--out',type=pathlib.Path,default=HERE/'CH40C_RESULTS');a.add_argument('--jobs',type=int,default=4);a.add_argument('--case',action='append')
    q=a.parse_args();r=run(q.archive,q.out,q.case,q.jobs);raise SystemExit(0 if r['failed']==0 and r['passed']==r['total'] else 1)