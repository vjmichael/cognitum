"""Isolated Linux exact assembly research control; not Cognitum's admitted kernel."""
import argparse, hashlib, io, json, os, platform, resource, statistics, subprocess, sys, time, zipfile
from fractions import Fraction as Q
from pathlib import Path
SOURCE='826e4b9459e4b70413ef8f0813a4c41c2b609fae'
ARCHIVES={14605961982:'51412521fd08597ab5f94d739b768863f36bde112b2ac6615b1434ac08ca8392',14606630117:'7819aae9ec856fd0a3cd938470fac0268497f01f44fbb618a0794616c469f3ea',14606755233:'60e3123ea0e1ec30066e3365ae5f99c47d23fe6dd56ca53ebab0f5994a8a329f',14605736313:'92cc5e4208e4b1139015db2cbb12bac98469b56bb139a6e70c7873cf8ce5022c'}
CASES=('DD','NN','DN','RR','variable-DD','variable-NR')
MESHES=(2,4,8,16)
def need(ok,msg):
    if not ok: raise ValueError(msg)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')
def corpus(bundle):
    outputs={}
    with zipfile.ZipFile(bundle) as outer:
        for aid,digest in ARCHIVES.items():
            raw=outer.read(f'archives/github-actions-artifact-{aid}.zip');need(sha(raw)==digest,'archive digest')
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                need(z.testzip() is None,'CRC');receipt=json.loads(z.read('receipt.json'))
                need(receipt['source_sha']==SOURCE and receipt['status']=='PASS','receipt custody')
                for case in CASES:
                    for n in MESHES:
                        key=f'{case}/{n}';name=key+'.matrix.json';raw=z.read(name)
                        need(sha(raw)==receipt['artifacts'][name],'matrix digest')
                        need(outputs.setdefault(key,raw)==raw,'cross-target matrix drift')
    need(len(outputs)==24,'corpus size')
    return [{'id':k,'input':{f:json.loads(v)[f] for f in ('problem','cuts')},'expected_sha256':sha(v)} for k,v in outputs.items()]
def add(a,b):return tuple((a[i] if i<len(a) else Q(0))+(b[i] if i<len(b) else Q(0)) for i in range(max(len(a),len(b))))
def mul(a,b):
    c=[Q(0)]*(len(a)+len(b)-1)
    for i,x in enumerate(a):
        for j,y in enumerate(b):c[i+j]+=x*y
    return tuple(c)
def basis(cuts):
    edges=(Q(0),*cuts,Q(1));g=(Q(0),)*3+edges+(Q(1),)*3
    for k in range(3,len(g)-4):
        a,b=g[k:k+2];h=b-a;prev=[(Q(int(i==k)),) for i in range(len(g)-1)]
        for d in range(1,4):
            cur=[]
            for i in range(len(g)-d-1):
                l=g[i+d]-g[i];r=g[i+d+1]-g[i+1];p=(Q(0),)
                if l:p=add(p,mul(prev[i],((a-g[i])/l,h/l)))
                if r:p=add(p,mul(prev[i+1],((g[i+d+1]-a)/r,-h/r)))
                cur.append(p)
            prev=cur
        yield a,b,prev
def weighted(a,b,c,h):return h*sum((v/Q(i+1) for i,v in enumerate(mul(mul(a,b),c))),Q(0))
def ldl(A,positive):
    n=len(A);L=[[Q(i==j) for j in range(n)] for i in range(n)];d=[]
    for j in range(n):
        v=A[j][j]-sum(L[j][k]**2*d[k] for k in range(j));need(v>0 if positive else v>=0,'LDL positivity');d.append(v)
        for i in range(j+1,n):
            a=A[i][j]-sum(L[i][k]*L[j][k]*d[k] for k in range(j));need(v or not a,'zero pivot incompatible');L[i][j]=a/v if v else Q(0)
    return d
def assemble(inp,support):
    p=inp['problem'];cuts=tuple(map(Q,inp['cuts']));ids=list(range(int(p['left'][0]=='D'),len(cuts)+4-int(p['right'][0]=='D')));n=len(ids)
    M=[[Q(0)]*n for _ in ids];K=[[Q(0)]*n for _ in ids];coeff=[list(map(Q,p[k])) for k in ('diffusion','potential','weight')]
    for a,b,polys in basis(cuts):
        h=b-a;v=[polys[i] for i in ids];active=[i for i in range(n) if not support or any(v[i])]
        d=[tuple(j*poly[j]/h for j in range(1,len(poly))) or (Q(0),) for poly in v];P,V,W=[(c[0]+c[1]*a,c[1]*h) for c in coeff]
        for i in active:
            for j in active:
                if j<i:continue
                M[i][j]=M[j][i]=M[i][j]+weighted(v[i],v[j],W,h)
                K[i][j]=K[j][i]=K[i][j]+weighted(d[i],d[j],P,h)+weighted(v[i],v[j],V,h)
    for i,k in ((0,'left'),(-1,'right')):
        if p[k][0]=='R':K[i][i]+=Q(p[k][1])
    null=p['left'][0]==p['right'][0]=='N' and coeff[1]==[0,0];md=ldl(M,True);sd=ldl(K,not null)
    if null:need(sd.count(0)==1 and all(sum(row)==0 for row in K),'null mode')
    return canonical(dict(profile='cognitum.kan.sturm_liouville_affine.v1',problem=p,cuts=inp['cuts'],dof=n,active_indices=ids,mass=[[str(x) for x in row] for row in M],stiffness=[[str(x) for x in row] for row in K],mass_ldl=list(map(str,md)),stiffness_ldl=list(map(str,sd)),constant_null_mode=null,degree=3,domain=['0','1'],execution_authorized=False))
def memory():
    status=Path('/proc/self/status').read_text();rss=int(next(l.split()[1] for l in status.splitlines() if l.startswith('VmRSS:')))*1024
    return {'rss_bytes':rss,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
def worker(file,route):
    data=json.loads(Path(file).read_bytes());before=memory();c=time.process_time_ns();w=time.perf_counter_ns()
    outputs=[assemble(row['input'],route=='support') for row in data];cpu=time.process_time_ns()-c;wall=time.perf_counter_ns()-w;after=memory()
    need(all(sha(out)==row['expected_sha256'] for out,row in zip(outputs,data)),'exact output mismatch')
    return dict(route=route,cpu_ns=cpu,wall_ns=wall,before=before,after=after,matrix_count=len(outputs),output_hashes=[sha(out) for out in outputs])
def fingerprint():
    binary=Path(sys.executable).resolve();stdlib=Path(os.__file__).parent
    files={str(p.relative_to(stdlib)):sha(p.read_bytes()) for p in sorted(stdlib.rglob('*.py')) if 'site-packages' not in p.parts and 'dist-packages' not in p.parts}
    return dict(python=sys.version,executable=str(binary),executable_sha256=sha(binary.read_bytes()),stdlib_py_count=len(files),stdlib_py_manifest_sha256=sha(canonical(files)),system=platform.platform(),machine=platform.machine(),affinity=sorted(os.sched_getaffinity(0)),isolated=sys.flags.isolated,no_site=sys.flags.no_site,external_python_dependencies=[],cpu_max=Path('/sys/fs/cgroup/cpu.max').read_text().strip(),memory_max=Path('/sys/fs/cgroup/memory.max').read_text().strip(),compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0] if Path('/usr/bin/g++').exists() else None,scope='Linux hosted fingerprint, not a portable OS image lock')
def run(bundle,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);need(sys.flags.isolated and sys.flags.no_site,'run with -I -S')
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});rows=corpus(bundle);data=canonical(rows);inp=out/'corpus.json';inp.write_bytes(data)
    env=fingerprint();env['script_sha256']=sha(Path(__file__).read_bytes());env['corpus_sha256']=sha(data);(out/'environment.json').write_text(json.dumps(env,indent=2)+'\n')
    samples=[]
    for i in range(3):
        for route in (('dense','support') if i%2==0 else ('support','dense')):
            start=time.perf_counter_ns();proc=subprocess.run([sys.executable,'-I','-S',str(Path(__file__).resolve()),'worker',str(inp),route],capture_output=True,text=True,check=True,timeout=120)
            result=json.loads(proc.stdout);result['launch_elapsed_ns']=time.perf_counter_ns()-start;result['pair']=i;samples.append(result)
    med={route:statistics.median(s['cpu_ns'] for s in samples if s['route']==route) for route in ('dense','support')}
    report=dict(source=SOURCE,corpus_sha256=sha(data),environment_sha256=sha((out/'environment.json').read_bytes()),matrix_count=len(rows),samples=samples,median_cpu_ns=med,cpu_ratio=med['dense']/med['support'],scope='independent pure-Python reconstruction; not accepted R/U kernel or native backend')
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='samples'}))
if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True);r=sub.add_parser('run');r.add_argument('bundle');r.add_argument('out');w=sub.add_parser('worker');w.add_argument('file');w.add_argument('route',choices=('dense','support'));a=p.parse_args()
    if a.mode=='run':run(a.bundle,a.out)
    else:print(json.dumps(worker(a.file,a.route)))
