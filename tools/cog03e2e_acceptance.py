"""Source-bound scoped E2E gate; inherited chain on hosted runners."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'cog03bc-artifacts'
def blob(path):
    b=path.read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def source_check():
    m=json.loads((ROOT/'docs/research/COG03E2E_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for p,h in m['git_blobs'].items():
        actual=blob(ROOT/p) if '--scoped-only' in sys.argv else subprocess.check_output(['git','rev-parse','HEAD:'+p],cwd=ROOT,text=True).strip()
        assert actual==h,p
    return m['git_blobs']
def main():
    scoped='--scoped-only' in sys.argv; before=source_check();sha=None
    if scoped:assert os.environ.get('GITHUB_ACTIONS')!='true'
    else:
        sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();assert sha==os.environ['COG03BC_EXPECTED_SHA']
        assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
        from tools import cog03e2d_acceptance as prior
        prior.main()
    OUT.mkdir(exist_ok=True);xml=OUT/'e2e-tests.xml';pilot=OUT/'e2e-pilot.json';paths=[xml,pilot]
    for tag,args in [('tests',['-m','pytest','-q','-ra','research_tests/hdc_e2e','--junitxml='+str(xml)]),('pilot',['-m','tools.cog03e2e_pilot','--quick','--out',str(pilot)])]:
        log=OUT/f'e2e-{tag}.log';paths.append(log)
        with log.open('wb') as f:subprocess.run([sys.executable,*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    tests=list(ET.parse(xml).iter('testcase'));assert len(tests)==31 and not any(c.find(t) is not None for c in tests for t in ('error','failure','skipped'))
    r=json.loads(pilot.read_text());assert len(r['uncertainty'])==16 and len(r['visual'])==8
    assert all(0<=x['coverage']<=1 and 0<=x['group_class_coverage']<=1 and 0<=x['mean_set_size']<=4 for x in r['uncertainty'])
    assert all(x['numeric_bytes']<=x['budget'] and len(x['phases'])==5 for x in r['visual'])
    assert any(x['merges']>0 for x in r['visual'] if x['novelty_floor']==.85 and x['method']=='merge')
    # Only the existing Linux 3.13 research dataset cell acquires real assets.
    # Other OS/Python cells run the fixture without torchvision/QNNPACK requirements.
    real=not scoped and os.environ.get('COG03C2C_DATASETS')=='1'
    if real:
        subprocess.run([sys.executable,'-m','pip','install','Pillow==12.3.0'],check=True,timeout=240)
        subprocess.run([sys.executable,'-m','pip','install','--no-deps','torchvision==0.25.0','--index-url','https://download.pytorch.org/whl/cpu'],check=True,timeout=240)
    close=OUT/'e2e-closeout.json';log=OUT/'e2e-closeout.log';paths.extend([close,log,close.with_suffix('.har.json')])
    import tempfile
    with tempfile.TemporaryDirectory(prefix='cog03e2e-') as td:
        flags=['--acquire'] if real else ['--fixture']+([] if scoped else ['--pixels-only'])
        with log.open('wb') as f:subprocess.run([sys.executable,'-m','tools.cog03e2e_closeout','--data',td,'--out',str(close),*flags],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1200 if real else 180)
    q=json.loads(close.read_text(encoding='utf8'));assert q['fixture']!=real
    expected=40 if real else (10 if scoped else 5)
    assert len(q['visual'])==expected and len(q['uncertainty'])==(3 if real else 1)
    assert all(x['numeric_bytes']<=x['budget'] and len(x['phases'])==5 for x in q['visual'])
    for x in q['uncertainty']:
        a,b,c=map(set,(x['fit_subjects'],x['cal_subjects'],x['test_subjects']))
        assert len(a)==11 and len(b)==10 and len(c)==9 and not (a&b or a&c or b&c)
        assert len(x['rows'])==24 and all(0<=r['coverage']<=1 and 0<=r['mean_set_size']<=6 for r in x['rows'])
    if real:
        m=q['metadata'];variant=m['quantization_variant'];assert variant in ('qat','ptq')
        prefix={'qat':'37f702c5','ptq':'7ebf99e0'}[variant]
        assert m['pretrained'] and m['checkpoint_sha256'].startswith(prefix) and m['checkpoint_sha256']==m['weights_sha256'] and len(m['har_sha256'])==64 and m['feature_shape']==[1797,1280] and m['feature_dtype']=='uint8'
        attempts=m['checkpoint_attempts'];assert attempts[-1]['verified'] and attempts[-1]['variant']==variant and attempts[-1]['sha256']==m['checkpoint_sha256']
        if variant=='ptq':assert any(a['variant']=='qat' and not a['verified'] for a in attempts) and not any(a['variant']=='qat' and a['verified'] for a in attempts)
        from tools.cog03e2e_closeout import visual_partition
        from sklearn.datasets import load_digits
        import numpy as np
        y=load_digits().target;assert len(m['feature_records'])==2
        for f in m['feature_records']:
            assert f['pretrained'] and f['quantization_variant']==variant and f['checkpoint_sha256']==m['checkpoint_sha256'] and f['feature_shape']==[1797,1280] and f['feature_dtype']=='uint8'
            _,tx,_,cal=visual_partition(y,f['seed']);assert f['calibration_indices']==(cal.tolist() if variant=='ptq' else []) and not np.intersect1d(tx,f['calibration_indices']).size
        assert {f['seed'] for f in m['feature_records']}=={1201,1207}
        assert all(r['n']==2947 for x in q['uncertainty'] for r in x['rows'])
    elif scoped:assert q['metadata']['pretrained'] is False and q['metadata']['feature_shape']==[240,1280]
    assert source_check()==before
    if sha:
        assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==sha
        assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
    (OUT/'e2e-result.json').write_text(json.dumps({'source_sha':sha,'source_blobs':before,'scoped_only':scoped,'real_assets_executed':real,'passed':True,'new_tests':len(tests),'expected_hosted_tests_with_inherited':585+len(tests),'production_enabled':False,'artifact_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}},indent=2)+'\n')
if __name__=='__main__':main()
