"""Source-bound E2G gate; hosted execution retains all E2F checks."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'cog03bc-artifacts'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source_check(scoped):
    m=json.loads((ROOT/'docs/research/COG03E2G_SOURCE_MANIFEST.json').read_text())['git_blobs']
    for p,h in m.items():
        b=(ROOT/p).read_bytes();actual=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        if actual!=h or (not scoped and subprocess.check_output(['git','rev-parse','HEAD:'+p],cwd=ROOT,text=True).strip()!=h):raise RuntimeError('source drift '+p)
    return m
def main():
    scoped='--scoped-only' in sys.argv
    if scoped and os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('hosted scope bypass')
    before=source_check(scoped);commit=None
    if not scoped:
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();assert commit==os.environ['COG03BC_EXPECTED_SHA'];assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
        from tools import cog03e2f_acceptance
        cog03e2f_acceptance.main()
    OUT.mkdir(exist_ok=True);xml=OUT/'e2g-tests.xml';pilot=OUT/'e2g-pilot.json';close=OUT/'e2g-closeout.json';files=[xml,pilot,close]
    for name,args in [('tests',['-m','pytest','-q','research_tests/hdc_e2g','--junitxml='+str(xml)]),('pilot',['-m','tools.cog03e2g_pilot','--quick','--out',str(pilot)]),('closeout',['-m','tools.cog03e2g_closeout','--quick','--out',str(close)])]:
        log=OUT/f'e2g-{name}.log';files.append(log)
        with log.open('wb') as f:subprocess.run([sys.executable,*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'));assert len(cases)==41 and not any(c.find(t) is not None for c in cases for t in ('failure','error','skipped'))
    rows=json.loads(pilot.read_text())['rows'];assert len(rows)==40
    from collections import Counter
    assert Counter(r['task'] for r in rows)=={'rl':5,'fed':17,'semi':5,'multi':4,'task_projection':4,'cascade':3,'cluster':2}
    rl=[r for r in rows if r['task']=='rl'];assert len({r['replay_sha256'] for r in rl})==1 and all(0<=r['success']<=r['n'] and r['numeric_bytes']>0 for r in rl)
    fed=[r for r in rows if r['task']=='fed'];assert len({r['partition_sha256'] for r in fed})==1 and len({r['split_sha256'] for r in rows if r['task']!='rl'})==1
    assert fed[0]['correct']==fed[1]['correct']
    for cond in ('clean','poison','bit_noise'):
        a={r['method']:r for r in fed if r['condition']==cond};assert a['packed_weighted']['wire_bytes']<a['weighted']['wire_bytes'] and a['packed_median']['wire_bytes']<a['median']['wire_bytes']
    semi=[r for r in rows if r['task']=='semi'];assert len({r['label_split'] for r in semi})==1 and all(0<=r['pseudo_correct']<=r['accepted'] for r in semi)
    assert all(0<=r['correct']<=r['n'] for r in rows if 'correct' in r)
    assert all(r['parity'] for r in rows if 'parity' in r)
    expanded=json.loads(close.read_text())['rows'];assert Counter(r['task'] for r in expanded)=={'rl':20,'fed':64,'binary':10}
    for r in expanded:
        if r['task']=='rl' and r['method']!='oracle':assert r['numeric_bytes']<=r['budget'] and 0<=r['success']<=r['n']
        if r['task']=='fed':assert r['estimated_client_model_workspace']<=r['budget'] and r['wire_bytes']>r['initial_wire_bytes']>0 and 0<=r['correct']<=r['n']
        if r['task']=='binary':assert r['numeric_bytes']<=r['budget'] and 0<=r['correct']<=r['n']
        if r['task']=='binary' and r['method']=='lazy':assert r['prediction_parity'] and r['fine_calls']==round(r['n']*r['route_fraction'])
    for cond in ('clean','label_flip','model_poison','dropout'):
        for budget in (8192,32768):
            for kind in ('raw','hdc'):
                arms={r['method']:r for r in expanded if r['task']=='fed' and r['condition']==cond and r['budget']==budget and r['kind']==kind}
                assert len(arms)==4 and len({r['partition_sha256'] for r in arms.values()})==1
                assert arms['packed_weighted']['wire_bytes']<arms['weighted']['wire_bytes'] and arms['packed_median']['wire_bytes']<arms['median']['wire_bytes']
    assert source_check(scoped)==before
    if commit:assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==commit and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
    (OUT/'e2g-result.json').write_text(json.dumps({'source_sha':commit,'source_blobs':before,'passed':True,'scoped_only':scoped,'new_tests':len(cases),'expected_hosted_tests_with_inherited':642+len(cases),'production_enabled':False,'artifact_hashes':{p.name:sha(p) for p in files}},indent=2)+'\n')
if __name__=='__main__':main()
