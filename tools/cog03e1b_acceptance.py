"""Dedicated E1B no-skip native compressed learning fidelity gate."""
import hashlib,json,subprocess,sys
from xml.etree import ElementTree as ET
from tools import cog03e1_acceptance as prior
ROOT=prior.ROOT;OUT=prior.OUT


def source_check():
    sha=prior.source_check();m=json.loads((ROOT/'docs/research/COG03E1B_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for p,h in m['git_blobs'].items():
        if subprocess.check_output(['git','rev-parse','HEAD:'+p],cwd=ROOT,text=True).strip()!=h:raise RuntimeError('E1B source drift '+p)
    return sha


def e1b_gate():
    before=source_check();OUT.mkdir(exist_ok=True);log=OUT/'e1b-tests.log';xml=OUT/'e1b-tests.xml'
    with log.open('wb') as f:subprocess.run([sys.executable,'-m','pytest','-q','-ra','--junitxml='+str(xml),'research_tests/hdc_e1b'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'))
    assert len(cases)==28 and not any(c.find(t) is not None for c in cases for t in ('failure','error','skipped'))
    f=OUT/'e1b-pilot.json';err=OUT/'e1b-pilot.log'
    with err.open('wb') as e:subprocess.run([sys.executable,'-m','tools.cog03e1b_pilot','--quick','--out',str(f)],cwd=ROOT,stdout=e,stderr=subprocess.STDOUT,check=True,timeout=180)
    r=json.loads(f.read_text(encoding='utf8'));rows={x['arm']:x for x in r['rows']};assert len(r['rows'])==len(rows)==12
    assert len({x['split'] for x in rows.values()})==1 and all(x['n']==36 and 0<=x['correct']<=x['n'] and x['retained_numeric_bytes']>0 for x in rows.values())
    for arm in ('vanilla','comp','quant','lehdc'):
        a=rows['packed_'+arm];b=rows['native_'+arm];assert a['disagreements']==0 and a['prediction_sha256']==b['prediction_sha256'] and a['retained_numeric_bytes']<b['native_inference_numeric_bytes']
    for arm in ('quant','lehdc'):assert rows['packed_'+arm]['native_weight_disagreements']==0
    for mode in ('dim','class'):
        a=rows['custom_sparse_'+mode];assert a['dense_disagreements']==0 and a['zero_fraction']>=.75
    after=source_check();assert before==after
    (OUT/'e1b-result.json').write_text(json.dumps({'schema':'cognitum.cog03e1b.acceptance.v1','source_sha':before,'source_after':after,'new_tests':len(cases),'expected_tests_with_inherited':447+len(cases),'passed':True,'smoke':r,'scope':'bounded software reference and actual pinned TorchHD comparisons; no hardware speed/energy or production enablement','artifact_hashes':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in [log,xml,f,err]},'production_enabled':False},indent=2)+'\n',encoding='utf8')


def main():
    source_check();prior.main();e1b_gate();source_check()
if __name__=='__main__':main()
