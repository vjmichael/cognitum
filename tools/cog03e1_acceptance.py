"""E1A learning fidelity guard, after the accepted D2B research chain."""
import hashlib,json,subprocess,sys
from xml.etree import ElementTree as ET
from tools import cog03d2b_acceptance as prior
ROOT=prior.ROOT;OUT=prior.OUT


def source_check():
    sha=prior.source_check();m=json.loads((ROOT/'docs/research/COG03E1A_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for p,h in m['git_blobs'].items():
        if subprocess.check_output(['git','rev-parse','HEAD:'+p],cwd=ROOT,text=True).strip()!=h:raise RuntimeError('E1A source drift '+p)
    return sha


def e1_gate():
    before=source_check();OUT.mkdir(exist_ok=True);log=OUT/'e1a-tests.log';xml=OUT/'e1a-tests.xml'
    with log.open('wb') as f:subprocess.run([sys.executable,'-m','pytest','-q','-ra','--junitxml='+str(xml),'research_tests/hdc_e1'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'))
    assert len(cases)==29 and not any(c.find(t) is not None for c in cases for t in ('failure','error','skipped'))
    f=OUT/'e1a-pilot.json';err=OUT/'e1a-pilot.log'
    with err.open('wb') as e:subprocess.run([sys.executable,'-m','tools.cog03e1_pilot','--quick','--out',str(f)],cwd=ROOT,stdout=e,stderr=subprocess.STDOUT,check=True,timeout=180)
    r=json.loads(f.read_text(encoding='utf8'));rows={x['arm']:x for x in r['rows']};assert len(r['rows'])==15 and len(rows)==15
    assert len({x['split'] for x in rows.values()})==1 and all(x['n']==36 for x in rows.values())
    for x in rows.values():
        if x.get('fit_failed'):
            assert x['arm']=='native_dist' and x['correct'] is None and 'topk()' in x['error']
        else:assert 0<=x['correct']<=x['n'] and sum(map(sum,x['confusion']))==x['n'] and x['numeric_bytes']>0
    for arm in ('vanilla','adapt','online'):assert rows['custom_'+arm]['native_prediction_disagreements']==0
    for arm in ('neural','dist'):
        assert rows['native_'+arm]['changed_projection_rows']==0
        assert rows['custom_regen_'+arm]['changed_projection_rows']>0
    assert rows['custom_rvfl']['native_prediction_disagreements']<=1
    after=source_check();assert before==after
    (OUT/'e1a-result.json').write_text(json.dumps({'schema':'cognitum.cog03e1a.acceptance.v1','source_sha':before,'source_after':after,'new_tests':len(cases),'expected_tests_with_inherited':418+len(cases),'passed':True,'smoke':r,'scope':'bounded software reference; native pinned defect regression; no full original paper replication or production enablement','artifact_hashes':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in [log,xml,f,err]},'production_enabled':False},indent=2)+'\n',encoding='utf8')


def main():
    source_check();prior.main();e1_gate();source_check()
if __name__=='__main__':main()
