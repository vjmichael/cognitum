"""Hash-bound native scientific wheel acceptance; network only during staging."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import venv
import warnings

ARCHIVE_SHA='4b07b8608fc65d00ccc232deac36d3bf55bb2049d0eaf4882219dda9c4ed940c'
RECORD=re.compile(r'([a-zA-Z0-9_-]+)==([^\s]+) --hash=sha256:([0-9a-f]{64})')

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def target():
    if platform.machine().lower() not in ('x86_64','amd64') or sys.implementation.name!='cpython':
        raise RuntimeError('Native CPython x64 required')
    system={'linux':'linux','win32':'win'}.get(sys.platform)
    py=sys.version_info[:2]
    if not system or py not in ((3,11),(3,13)):
        raise RuntimeError('Unsupported target')
    return f'{system}-x64-py{py[0]}{py[1]}'

def records(lock):
    out=[]
    for line in lock.read_text(encoding='utf-8').splitlines():
        if not line.strip():continue
        match=RECORD.fullmatch(line)
        if not match:raise ValueError('Unpinned or malformed lock entry')
        out.append(match.groups())
    if len({a for a,_,_ in out})!=len(out) or len({h for _,_,h in out})!=len(out):
        raise ValueError('Duplicate lock entry')
    return out

def stage(rows, directory):
    directory.mkdir()
    for name,version,sha in rows:
        endpoint=f'https://pypi.org/pypi/{urllib.parse.quote(name)}/{urllib.parse.quote(version)}/json'
        with urllib.request.urlopen(endpoint,timeout=60) as response:
            data=json.load(response)
        matches=[u for u in data['urls'] if u['digests']['sha256']==sha and u['packagetype']=='bdist_wheel']
        if len(matches)!=1:raise RuntimeError(f'Cannot rehydrate exact wheel: {name} {version}')
        item=matches[0]; filename=item['filename']; url=item['url']
        if not filename.endswith('.whl') or '/' in filename or '\\' in filename or urllib.parse.urlparse(url).scheme!='https' or urllib.parse.urlparse(url).hostname!='files.pythonhosted.org':
            raise RuntimeError('Unexpected wheel URL/name')
        dest=directory/filename
        with urllib.request.urlopen(url,timeout=120) as response, dest.open('xb') as file:
            while chunk:=response.read(1024*1024):file.write(chunk)
        if digest(dest)!=sha:raise RuntimeError(f'Wheel hash mismatch: {name}')

def verify(rows,directory):
    got={p.name:digest(p) for p in directory.iterdir() if p.is_file() and p.suffix=='.whl'}
    if len(got)!=len(rows) or set(got.values())!={h for _,_,h in rows}:
        raise RuntimeError('Wheelhouse differs from uploaded lock')
    return got

def probe():
    import numpy as np, networkx as nx, scipy, ortools, google.protobuf
    from scipy.optimize import milp,Bounds,LinearConstraint,linprog
    from ortools.sat.python import cp_model
    from google.protobuf.struct_pb2 import Struct
    if sys.version_info>=(3,12):
        import arviz_stats as az
    else:
        with warnings.catch_warnings():
            warnings.filterwarnings('default',message=r'\s*ArviZ is undergoing a major refactor',category=FutureWarning,module=r'arviz')
            import arviz as az
    a=np.random.default_rng(42).normal(size=(4,80))
    stats={}
    for name,kwargs in [('rhat',{'method':'rank'}),('ess',{'method':'bulk'}),('ess',{'method':'tail','prob':(.05,.95)}),('mcse',{'method':'mean'})]:
        val=float(getattr(az,name)(a,**kwargs)); assert np.isfinite(val) and val>0
        stats[name+':'+kwargs['method']]=val
    g=nx.DiGraph();g.add_weighted_edges_from([('a','b',2),('b','c',3),('a','c',7)])
    assert nx.shortest_path_length(g,'a','c',weight='weight')==5
    f=nx.DiGraph();f.add_node('s',demand=-3);f.add_node('t',demand=3);f.add_edge('s','t',capacity=3,weight=2)
    assert nx.network_simplex(f)[0]==6
    m=cp_model.CpModel();x=m.new_int_var(0,5,'x');m.maximize(x);m.add(x<=3)
    s=cp_model.CpSolver();s.parameters.num_search_workers=1
    assert s.solve(m)==cp_model.OPTIMAL and s.value(x)==3
    r=milp(c=[-1,-2],integrality=[1,1],bounds=Bounds([0,0],[3,3]),constraints=LinearConstraint([[1,1]],-np.inf,4))
    assert r.success and abs(r.fun+7)<1e-8
    r=linprog([-1],bounds=[(0,3)],method='highs');assert r.success and abs(r.fun+3)<1e-8
    p=Struct();p['value']=3;assert Struct.FromString(p.SerializeToString())['value']==3
    absent=not {'arviz','arviz_plots','matplotlib'}.intersection(sys.modules)
    if sys.version_info>=(3,12):assert absent
    print(json.dumps({'target':target(),'versions':{'numpy':np.__version__,'networkx':nx.__version__,'scipy':scipy.__version__,'ortools':ortools.__version__,'protobuf':google.protobuf.__version__,'diagnostics':az.__version__},'statistics':stats,'checks':['shortest_path','min_cost_flow','cp_sat','milp','highs_lp','protobuf'],'plot_modules_absent':absent,'status':'PASS'},indent=2))

def run(args,log,cwd=None):
    with log.open('w',encoding='utf-8') as f:
        result=subprocess.run([str(v) for v in args],stdout=f,stderr=subprocess.STDOUT,cwd=cwd,check=False,timeout=600)
    if result.returncode:raise RuntimeError(f'Command failed ({result.returncode}): {log}')

def main():
    if len(sys.argv)==2 and sys.argv[1]=='--probe':
        probe();return
    p=argparse.ArgumentParser();p.add_argument('--locks',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--wheelhouse',type=Path);p.add_argument('--rehydrate',action='store_true');p.add_argument('--source-root',type=Path)
    a=p.parse_args()
    if bool(a.wheelhouse)==a.rehydrate:p.error('Choose exactly one wheelhouse source')
    name=target();lock=(a.locks/f'{name}.txt').resolve();rows=records(lock)
    assert len(rows)==(26 if sys.version_info[:2]==(3,11) else 19)
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    wheels=a.wheelhouse.resolve() if a.wheelhouse else out/'wheels'
    receipt={'target':name,'python':sys.version,'source_archive_sha256':ARCHIVE_SHA,'lock_sha256':digest(lock),'wheel_origin':'PyPI rehydrated by exact uploaded hashes' if a.rehydrate else 'provided wheelhouse','status':'OPEN','profiles':[]}
    try:
        if a.rehydrate:stage(rows,wheels)
        receipt['wheel_hashes']=verify(rows,wheels)
        profiles={'full':lock}
        if sys.version_info[:2]==(3,13):
            minimal=out/'stats-only.txt';minimal.write_text('\n'.join(f'{n+"[xarray]" if n=="arviz-stats" else n}=={v} --hash=sha256:{h}' for n,v,h in rows if n not in ('arviz','arviz-plots'))+'\n',encoding='utf-8');profiles['stats-only']=minimal
        for label,profile in profiles.items():
            env=out/label;venv.EnvBuilder(with_pip=True).create(env)
            py=env/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
            run([py,'-m','pip','--isolated','install','--disable-pip-version-check','--no-index','--find-links',wheels,'--only-binary=:all:','--require-hashes','-r',profile],out/f'{label}-install.log')
            run([py,'-m','pip','--isolated','check','--disable-pip-version-check'],out/f'{label}-pip-check.log')
            run([py,'-W','error',Path(__file__).resolve(),'--probe'],out/f'{label}-probe.json')
            if a.source_root:
                root=a.source_root.resolve()
                commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
                expected=os.environ.get('GITHUB_SHA')
                if expected and expected!=commit:raise RuntimeError('Wrong source commit')
                if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=root,text=True).strip():raise RuntimeError('Modified source checkout')
                receipt['source_commit']=commit
                for pattern in ('test_c13_p4_diagnostics.py','test_c13_diagnostics_compatibility.py'):
                    if not (root/'tests'/pattern).is_file():raise RuntimeError('Required tests absent')
                    run([py,'-W','error','-m','unittest','discover','-s','tests','-p',pattern,'-v'],out/f'{label}-{pattern}.log',cwd=root)
            receipt['profiles'].append({'name':label,'offline_install':'PASS','pip_check':'PASS','native_probe':'PASS','source_tests':'PASS' if a.source_root else 'NOT_RUN'})
        receipt['status']='PASS'
    finally:
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
