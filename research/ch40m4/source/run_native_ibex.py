#!/usr/bin/env python3
"""Bounded research-only IBEX baseline for frozen C14 Minibex inputs.

Exits with nonzero for invalid package, case-set mismatch, native crashes, or
missing output. It never promotes the IBEX interval to a CH40 certificate.
"""
import argparse,hashlib,json,re,resource,subprocess,time,zipfile
from pathlib import Path
ROOT_CASES=15
RX=re.compile(r'f\* in\s*\[([^,\]\n]+),([^\]\n]+)\]')
ANSI=re.compile(r'\x1b\[[0-9;]*m')
def resource_limits():
    resource.setrlimit(resource.RLIMIT_AS,(int(2.5*1024**3),)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(30,31))
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--ibexopt',type=Path,required=True)
    p.add_argument('--frozen-model-zip',type=Path,required=True)
    p.add_argument('--workdir',type=Path,required=True)
    p.add_argument('--solver-seconds',type=float,default=1.0)
    p.add_argument('--wall-seconds',type=float,default=28.0)
    p.add_argument('--cases',nargs='*',default=None)
    args=p.parse_args()
    if not args.ibexopt.is_file():p.error('missing native ibexopt')
    args.workdir.mkdir(parents=True,exist_ok=True)
    z=zipfile.ZipFile(args.frozen_model_zip)
    entries=sorted(n for n in z.namelist() if n.startswith('ibex_models/') and n.endswith('.bch'))
    if len(entries)!=ROOT_CASES or len(set(entries))!=ROOT_CASES:p.error('frozen model archive must contain exactly 15 unique files')
    if args.cases:
        allowed=set(args.cases)
        if not allowed.issubset({Path(n).stem for n in entries}):p.error('unknown case name')
        entries=[n for n in entries if Path(n).stem in allowed]
    result_path=args.workdir/'IBEX_NATIVE_RESULTS.json'
    if result_path.exists():
        old=json.loads(result_path.read_text())
        if old.get('protocol')!='CH40M4-IBEX-NATIVE-BOUNDED-V1':p.error('existing results protocol mismatch')
        results=old['cases']
    else:results={}
    for name in entries:
        case=Path(name).stem
        data=z.read(name);digest=hashlib.sha256(data).hexdigest()
        if case in results and results[case].get('model_sha256') != digest:p.error('frozen case content changed: '+case)
        model_path=args.workdir/(case+'.bch');model_path.write_bytes(data)
        cmd=[str(args.ibexopt.resolve()),'--timeout='+str(args.solver_seconds),'--simpl=0','--abs-eps-f=0.05','-o',str(args.workdir/(case+'.cov')),str(model_path)]
        start=time.monotonic()
        try:
            proc=subprocess.run(cmd,cwd=args.workdir,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=args.wall_seconds,preexec_fn=resource_limits)
            text=ANSI.sub('',proc.stdout)
            (args.workdir/(case+'.log')).write_text(text)
            match=RX.search(text)
            endpoints=[float(match.group(1)),float(match.group(2))] if match else None
            if endpoints is not None and not (endpoints[0] <= endpoints[1]):raise ValueError('nonmonotone optimizer interval')
            passed=proc.returncode == 0 and match is not None and 'file loaded:' in text
            row={'case':case,'model_sha256':digest,'status':'NATIVE_INTERVAL_REPORTED' if passed else 'NO_VALID_RESULT','returncode':proc.returncode,'wall_seconds':round(time.monotonic()-start,3),'interval_min_negative_firth':endpoints,'reported_gap':endpoints[1]-endpoints[0] if passed else None,'target_0_05_reached':bool(passed and endpoints[1]-endpoints[0]<=0.05),'native_log_file':case+'.log'}
        except subprocess.TimeoutExpired:
            row={'case':case,'model_sha256':digest,'status':'WALL_TIMEOUT','wall_seconds':round(time.monotonic()-start,3),'target_0_05_reached':False}
        results[case]=row
        tmp=result_path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps({'protocol':'CH40M4-IBEX-NATIVE-BOUNDED-V1','scope':'native IBEX-reported intervals ONLY; no independent global certificate','engine':'IBEX 2.9.1 Filib+SoPlex','cases':results},indent=2)+'\n')
        tmp.replace(result_path)
        print(case,row['status'],row.get('reported_gap'),flush=True)
    done=len(results)
    if not args.cases and done!=ROOT_CASES:raise SystemExit('not all 15 cases completed')
    if any(v['status']!='NATIVE_INTERVAL_REPORTED' for v in results.values()):raise SystemExit('some native models did not return intervals')
if __name__=='__main__':main()
