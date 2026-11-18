"""E2F source-bound scope; existing E2E real-input gate preserved when hosted."""
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'cog03bc-artifacts'

def blob(p):
    b=p.read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()

def source_check(scoped):
    m=json.loads((ROOT/'docs/research/COG03E2F_SOURCE_MANIFEST.json').read_text(encoding='utf8'))['git_blobs']
    for p,h in m.items():
        v=blob(ROOT/p) if scoped else subprocess.check_output(['git','rev-parse','HEAD:'+p],cwd=ROOT,text=True).strip()
        if v!=h:raise RuntimeError('E2F source drift '+p)
    return m

def main():
    scoped='--scoped-only' in sys.argv
    if scoped and os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('hosted scoped bypass prohibited')
    before=source_check(scoped);sha=None
    if not scoped:
        sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        if sha!=os.environ['COG03BC_EXPECTED_SHA'] or subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip():raise RuntimeError('unexpected source')
        from tools import cog03e2e_acceptance as prior
        prior.main()
    OUT.mkdir(exist_ok=True);xml=OUT/'e2f-tests.xml';pilot=OUT/'e2f-pilot.json';files=[xml,pilot]
    for name,args in [('tests',['-m','pytest','-q','-ra','research_tests/hdc_e2f','--junitxml='+str(xml)]),('pilot',['-m','tools.cog03e2f_pilot','--quick','--out',str(pilot)])]:
        log=OUT/f'e2f-{name}.log';files.append(log)
        with log.open('wb') as f:subprocess.run([sys.executable,*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'))
    assert len(cases)==26 and not any(c.find(t) is not None for c in cases for t in ('failure','error','skipped'))
    r=json.loads(pilot.read_text(encoding='utf8'));rows=r['rows'];assert len(rows)==39
    for task,conditions,n,arms in [('categorical',('clean','unseen_length','insert_delete_repeat'),12,6),('waveform',('clean','longer','time_warp'),15,7)]:
        for condition in conditions:
            cohort=[x for x in rows if x['task']==task and x['condition']==condition]
            assert len(cohort)==arms and len({x['method'] for x in cohort})==arms and len({x['split_sha256'] for x in cohort})==1
            assert all(x['n']==n and 0<=x['correct']<=n and x['retained_numeric_bytes']>0 and x['predict_seconds']>=0 for x in cohort)
    assert all(0<=x['rank1_agreement']<=1 for x in rows if 'rank1_agreement' in x)
    real=not scoped and os.environ.get('COG03C2C_DATASETS')=='1'
    close=OUT/'e2f-closeout.json';log=OUT/'e2f-closeout.log';files.extend([close,log])
    with tempfile.TemporaryDirectory(prefix='cog03e2f-') as td:
        flags=['--data',td,'--acquire'] if real else ['--quick']
        with log.open('wb') as f:subprocess.run([sys.executable,'-m','tools.cog03e2f_closeout','--resource','--out',str(close),*flags],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=900 if real else 180)
    q=json.loads(close.read_text(encoding='utf8'));assert q['fixture']!=real and len(q['rows'])==(180 if real else 60) and len(q['har'])==(3 if real else 1)
    from tools.cog03e2f_closeout import HAR_SHA
    assert q['har_sha256']==(HAR_SHA if real else None)
    for h in q['har']:
        a,b,c=map(set,(h['fit_subjects'],h['cal_subjects'],h['test_subjects']));assert (len(a),len(b),len(c))==(11,10,9) and not (a&b or a&c or b&c)
        assert len(h['rows'])==32
        for cond in ('calibration','official_test'):
            subset=[r for r in h['rows'] if r['condition']==cond];assert len(subset)==16 and len({r['split_sha256'] for r in subset})==1
            assert {r['method'] for r in subset}=={'raw_logistic','raw_packed','ldn_logistic','ldn_packed','token_hmm','token_duration_hmm','token_bigram_logistic','token_bigram_packed'}
            if real and cond=='official_test':assert all(r['n']==2947 and set(r['subjects'])==c for r in subset)
    rows=q['rows']+[r for h in q['har'] for r in h['rows']]
    assert all(r['retained_bytes']>0 and (r['eligible']==(r['retained_bytes']<=r['budget'])) for r in rows)
    assert all(0<=r['correct']<=r['n'] and r['seconds']>=0 for r in rows if r['eligible'])
    assert len(q['resources'])==4 and all(r['peak_process_bytes']>=r['peak_before_bytes']>0 and r['seconds']>=0 and len(r['rows'])==3 for r in q['resources'])
    files.extend(OUT/f'e2f-closeout-{r["arm"]}.json' for r in q['resources'])
    if real:assert any(r['method']=='ldn_packed' and r['condition']=='official_test' and r['eligible'] for r in rows if r['task']=='har')
    assert source_check(scoped)==before
    if sha:
        assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==sha
        assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
    (OUT/'e2f-result.json').write_text(json.dumps(dict(source_sha=sha,source_blobs=before,scoped_only=scoped,passed=True,real_har_executed=real,new_tests=len(cases),expected_hosted_tests_with_inherited=616+len(cases),production_enabled=False,artifact_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
