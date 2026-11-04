#!/usr/bin/env python3
"""Bounded SoPlex/IBEX optimizer on hash-pinned CH40M2 original Minibex models.
Upstream solver output is *not* independently verified and is not a Cognitum certificate.
"""
import hashlib,json,pathlib,re,resource,subprocess,sys,time,zipfile
ROOT=pathlib.Path(__file__).resolve().parent
REFERENCE=pathlib.Path('/mnt/data/Cognitum_CH40M2_Standard_Solver_Adapters_All15_2026-11-03.zip')
DEST=ROOT/'ibexopt15_soplex_canonical.json'
F_RE=re.compile(r'f\* in\s*\[\s*([^,\]]+)\s*,\s*([^\]]+)\]')

def limits():
 resource.setrlimit(resource.RLIMIT_AS,(int(1.5*2**30),)*2)
 resource.setrlimit(resource.RLIMIT_CPU,(24,25))

def main():
 zs=zipfile.ZipFile(REFERENCE)
 allnames=sorted(x.rsplit('/',1)[-1].removesuffix('.bch') for x in zs.namelist() if x.startswith('ibex_models/') and x.endswith('.bch'))
 targets=sys.argv[1:] or allnames
 if len(set(targets))!=len(targets) or any(t not in allnames for t in targets):raise ValueError('Unrecognized/duplicate original case')
 out=json.loads(DEST.read_text()) if DEST.exists() else {'protocol':'CH40M4-IBEX-SOPLEX-15-FROZEN-MODELS','claim':'SMOKE ONLY: no independent global verification','backend':'IBEX 2.9.1 / SoPlex 4.0.2 / Filib','cases':{}}
 for name in targets:
  model=ROOT/'models'/(name+'.bch')
  orig=zs.read('ibex_models/'+model.name)
  if model.read_bytes()!=orig:raise ValueError('Frozen CH40M2 model modified: '+name)
  st=time.monotonic()
  cmd=[str(ROOT/'build_soplex/bin/ibexopt'),'--rigor','--simpl=0','--timeout=0.4','--abs-eps-f=0.05',str(model)]
  try:
   q=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,cwd=str(ROOT/'models'),timeout=27,preexec_fn=limits)
   raw=q.stdout;g=F_RE.search(raw)
   bounds=[float(v.strip()) for v in g.groups()] if g else None
   ok=(q.returncode==0 and bounds is not None and bounds[0]<=bounds[1])
   row={'model_sha256':hashlib.sha256(orig).hexdigest(),'status':'EXECUTED_UNVERIFIED' if ok else 'UNRESOLVED','exit':q.returncode,'terminal':'TIME_LIMIT' if 'time limit' in raw else 'OPTIMIZATION_SUCCESS' if 'optimization successful' in raw else 'OTHER','interval_reported':bounds,'gap_reported':bounds[1]-bounds[0] if bounds else None,'wall_seconds':round(time.monotonic()-st,4),'native_output_tail':raw[-2000:],'independent_proof_accepted':False}
  except Exception as e:row={'model_sha256':hashlib.sha256(orig).hexdigest(),'status':'UNRESOLVED','error':repr(e),'wall_seconds':round(time.monotonic()-st,4),'independent_proof_accepted':False}
  out['cases'][name]=row; DEST.write_text(json.dumps(out,indent=2)+'\n')
  print(name, row['status'],row.get('terminal'),round(row['wall_seconds'],2),'gap',row.get('gap_reported'),flush=True)
if __name__=='__main__':main()
