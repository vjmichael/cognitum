"""E2G line-ending repair and mandatory RGB qualification on existing dataset cell."""
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from tools import cog03e2g_acceptance as prior
ROOT=prior.ROOT;OUT=prior.OUT

def source_check(scoped):
    m=json.loads((ROOT/'docs/research/COG03E2G_RGB_SOURCE_MANIFEST.json').read_text(encoding='utf8'))['git_blobs']
    for name,expected in m.items():
        b=(ROOT/name).read_bytes();actual=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        if actual!=expected or (not scoped and subprocess.check_output(['git','rev-parse','HEAD:'+name],cwd=ROOT,text=True).strip()!=expected):raise RuntimeError('RGB source drift '+name)
    prior.source_check(scoped)
    return m

def main():
    scoped='--scoped-only' in sys.argv
    if scoped and os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('no scoped hosted bypass')
    before=source_check(scoped);sha=None
    if not scoped:
        sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        if sha!=os.environ['COG03BC_EXPECTED_SHA']:raise RuntimeError('unexpected SHA')
    prior.main();OUT.mkdir(exist_ok=True)
    xml=OUT/'e2g-rgb-tests.xml';result=OUT/'e2g-rgb.json';log=OUT/'e2g-rgb.log';tlog=OUT/'e2g-rgb-tests.log'
    with tlog.open('wb') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/hdc_e2g_rgb','--junitxml='+str(xml)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    tests=list(ET.parse(xml).iter('testcase'))
    assert len(tests)==8 and not any(c.find(t) is not None for c in tests for t in ('error','failure','skipped'))
    real=not scoped and os.environ.get('COG03C2C_DATASETS')=='1'
    with tempfile.TemporaryDirectory(prefix='cog-e2g-cifar-') as td:
        with log.open('wb') as f:subprocess.run([sys.executable,'-m','tools.cog03e2g_cifar','--data',td,'--out',str(result),*(['--acquire'] if real else ['--fixture'])],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=2700 if real else 180)
    data=json.loads(result.read_text(encoding='utf8'));rows=data['rows'];assert data['complete'] is True and data['fixture']!=real and len(rows)==(120 if real else 5)
    assert all(r['numeric_bytes']<=r['budget'] and len(r['phases'])==5 and all(-1<=p['ari']<=1 for p in r['phases']) for r in rows)
    if real:
        from tools.cog03e2g_cifar import CIFAR_SHA,WEIGHT_SHA
        assert data['cifar_sha256']==CIFAR_SHA and data['checkpoint_sha256']==WEIGHT_SHA
        f=[r for r in data['records'] if 'variant' in r];assert len(f)==4 and all(r['pretrained'] and r['shape']==[2064,1280] and r['dtype']==('uint8' if r['variant']=='ptq' else 'float32') for r in f)
        for r in data['records']:
            if 'train_indices' in r:assert len(r['train_indices'])==len(r['test_indices'])==1000 and len(r['calibration_indices'])==64 and not set(r['train_indices'])&set(r['calibration_indices'])
        assert len(data['supervised_probes'])==6
    assert source_check(scoped)==before
    if sha:assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==sha and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
    (OUT/'e2g-rgb-result.json').write_text(json.dumps(dict(source_sha=sha,scoped_only=scoped,new_tests=len(tests),expected_hosted_tests=683+len(tests),real_cifar_executed=real,passed=True,production_enabled=False,artifact_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [xml,result,log,tlog]}),indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
