"""Same-head accepted R/U conformance; no native solver implementation."""
import argparse, hashlib, json, os, platform, subprocess, sys
from fractions import Fraction as Q
from pathlib import Path
from cognitum.research import kan_sturm_liouville as r, kan_certified_spectrum as u

ROOT=Path(__file__).resolve().parents[2]
REF=ROOT/'docs/research/cog05c'
INPUT_SHA='2f19c951459db914b07267e8da3016b4e0c0005cd1164e9425c0301e126cc238'
PINS={"cognitum/mel/tensor_field.py":"a94e1d8d8a0c202668fc84da6e4354eacdb43891","cognitum/mel/tensor_field_pb2.py":"461c107ff36e7295c022c132c40f0500029930e5","cognitum/research/kan_certified_spectrum.py":"875ad2dc1348a90f35109cab1dbaaa0490f9c2e7","cognitum/research/kan_elliptic_certificate.py":"0f2b725c2f0c7a886aaf4cbf03140d31d50dde6c","cognitum/research/kan_function_metrics.py":"b55215b30249aafada8342b7d794895af17143bd","cognitum/research/kan_spacetime_certificate.py":"12b699c5d6aafd1d1db5c14672fa1391610957eb","cognitum/research/kan_sturm_liouville.py":"92e4a2e4ae5447427546275f1d2341b67d9b5029","cognitum/research/kan_transient_certificate.py":"7d39f459aa8459e02776f94b91ad59364cf633d7","cognitum/research/kan_weak_form.py":"96eab091950fc86ea700c756a17c655220f83e57"}
def need(ok,msg):
    if not ok:raise ValueError(msg)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def decode(x):return Q(x) if type(x) is str else x
def problem(row):
    p=row['problem']
    return r.Problem(**{k:(v[0],decode(v[1])) if k in ('left','right') else tuple(map(decode,v)) for k,v in p.items()}),tuple(map(decode,row['cuts']))
def reject(fn):
    try:fn()
    except ValueError as e:return str(e)
    raise RuntimeError('unexpected acceptance')
def compare(row,expected):
    p,c=problem(row);a=r.assemble(p,c);b=u.assemble_supported(p,c)
    need(a==b and sha(a)==expected,'reference mismatch '+row['id'])
    need(r.replay(p,c,a),'replay')
    d=json.loads(a)
    changed=dict(d);changed['mass']=[list(v) for v in d['mass']];changed['mass'][0][0]=str(Q(changed['mass'][0][0])+1)
    corrupt=json.dumps(changed,sort_keys=True,separators=(',',':')).encode('ascii')
    controls=[reject(lambda:r.replay(p,c,a+b' ')),reject(lambda:r.replay(p,c,corrupt))]
    return a,dict(id=row['id'],sha256=sha(a),dof=d['dof'],replay_refusals=controls)
def run(prior,out):
    prior=Path(prior).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    head=git('rev-parse','HEAD');need(not os.getenv('GITHUB_SHA') or os.environ['GITHUB_SHA']==head,'source SHA');need(not git('status','--porcelain','--untracked-files=no'),'tracked drift')
    for path,blob in PINS.items():need(git('rev-parse',head+':'+path)==blob,'accepted source pin '+path)
    oldraw=(prior/'receipt.json').read_bytes();old=json.loads(oldraw)
    need(old['source_sha']==head and old['status']=='PASS' and old['totals']==dict(tests=20,errors=0,failures=0,skipped=0),'same-head U prerequisite')
    for name,digest in old['artifacts'].items():
        p=(prior/name).resolve();need(p.is_relative_to(prior) and p.is_file() and sha(p.read_bytes())==digest,'prior artifact integrity')
    raw=(REF/'inputs.json').read_bytes();need(sha(raw)==INPUT_SHA,'frozen input digest');corpus=json.loads(raw);need(corpus['seed']==2026111905 and len(corpus['positive'])==27 and len(corpus['negative'])==24,'corpus')
    expected=dict(line.split() for line in (REF/'expected.tsv').read_text().splitlines());need(set(expected)=={v['id'] for v in corpus['positive']},'held-out inventory')
    rows=[]
    for v in corpus['positive']:
        a,record=compare(v,expected[v['id']]);(out/(v['id']+'.json')).write_bytes(a);rows.append(record)
    historic=[]
    for case in old['cases']:
        for row in case['rows']:
            name=f"{case['case']}/{row['cells']}.matrix.json";a=(prior/name).read_bytes();d=json.loads(a)
            v=dict(id=f"{case['case']}/{row['cells']}",problem=d['problem'],cuts=d['cuts'])
            b,rec=compare(v,row['matrix_sha256']);need(a==b,'historic receipt bytes');historic.append(rec)
    need(len(historic)==24,'historic inventory')
    negative=[]
    for v in corpus['negative']:
        results=[]
        for fn in (r.assemble,u.assemble_supported):
            results.append(reject(lambda:fn(*problem(v))))
        negative.append(dict(id=v['id'],refusals=results))
    budget=[reject(lambda:r.o._bounded(Q(1<<8192))),reject(lambda:r.o._bounded(Q(1,1<<8192)))]
    p,c=problem(corpus['positive'][0]);budget.append(reject(lambda:r.replay(p,c,b'x'*(r.MAX_RECEIPT+1))))
    receipt=dict(source_sha=head,status='PASS',python=sys.version,platform=platform.platform(),prior_u_sha256=sha(oldraw),inputs_sha256=INPUT_SHA,source_pins=PINS,held_out=rows,historic=historic,negative=negative,budget_refusals=budget,execution_authorized=False,native_backend_implemented=False,artifacts={p.name:sha(p.read_bytes()) for p in sorted(out.glob('*.json'))})
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print('51 exact matrix comparisons; 48 invalid route refusals; 102 replay refusals; 3 budget refusals')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True);a=p.parse_args();run(a.prior,a.out)
