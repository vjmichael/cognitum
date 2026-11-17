"""Dedicated CPU HDC acceptance; actual dependency, no skips, no production route."""
import hashlib, json, os, platform, subprocess, sys, time
from importlib.metadata import version
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'cog03bc-artifacts'


def run(*args):
    subprocess.run([sys.executable,*args],cwd=ROOT,check=True)


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def source_check():
    sha=git('rev-parse','HEAD')
    if sha!=os.environ.get('COG03BC_EXPECTED_SHA') or git('status','--porcelain','--untracked-files=no'):
        raise RuntimeError('tracked source differs from expected checkout')
    manifest=json.loads((ROOT/'docs/research/COG03BC_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for p,blob in manifest['git_blobs'].items():
        if git('rev-parse','HEAD:'+p)!=blob:raise RuntimeError('source drift: '+p)
    for p,blob in manifest['preserved_recovered_blobs'].items():
        if git('rev-parse','HEAD:'+p)!=blob:raise RuntimeError('historical source drift: '+p)
    return sha


def install():
    # Only this isolated hosted research job receives PyTorch, not production or COG-07.
    run('-m','pip','install','numpy==2.3.5','scipy==1.17.0','pandas==2.2.3','requests==2.32.5','tqdm==4.67.3','openpyxl==3.1.5','pytest==9.0.2')
    run('-m','pip','install','torch==2.10.0','--index-url','https://download.pytorch.org/whl/cpu')
    wheel=OUT/'wheels'/'torch_hd-5.8.4-py3-none-any.whl'
    run('-m','pip','download','--no-deps','--only-binary=:all:','--dest',str(wheel.parent),'torch-hd==5.8.4')
    if hashlib.sha256(wheel.read_bytes()).hexdigest()!='734a2d4673af4418dd75908402c81d0221335bc96a9b8c07cfba4d86db6dd175':raise RuntimeError('unexpected TorchHD wheel')
    run('-m','pip','install','--no-deps','--no-index',str(wheel))
    run('-m','pip','check')
    wheel.unlink()


def main():
    OUT.mkdir(exist_ok=True)
    sha=source_check()
    if '--installed' not in sys.argv:install()
    import torch,torchhd,numpy,scipy
    if version('torch-hd')!='5.8.4' or torch.version.cuda is not None or torch.version.hip is not None:
        raise RuntimeError('actual reviewed CPU TorchHD is required')
    report={'schema':'cognitum.cog03bc.acceptance.v1','source_sha':sha,'platform':platform.platform(),'python':sys.version,
            'versions':{k:version(k) for k in ('torch','torch-hd','numpy','scipy','pytest')},'production_enabled':False,'steps':[]}
    def save():(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    def step(name,args):
        t=time.perf_counter();path=OUT/(name+'.log')
        with path.open('wb') as log:code=subprocess.run([sys.executable,*args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
        print(path.read_text(encoding='utf8',errors='replace')[-4000:]);report['steps'].append({'name':name,'exit':code,'seconds':time.perf_counter()-t,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()});save()
        if code:raise RuntimeError(name+' failed')
    save()
    xml=OUT/'tests.xml'
    step('dedicated_research',['-m','pytest','-q','-ra','--junitxml='+str(xml),'research_tests/hdc'])
    cases=list(ET.parse(xml).iter('testcase'))
    if not cases or any(c.find('skipped') is not None or c.find('failure') is not None or c.find('error') is not None for c in cases):raise RuntimeError('research cases missing, failed or skipped')
    # Bound minimum to actual tested cohort; all native cases required.
    if len(cases)<226 or sum('test_native_shared_operands[' in c.attrib.get('name','') for c in cases)!=8:raise RuntimeError('incomplete native cohort')
    report['tests_passed']=len(cases)
    step('capacity_smoke',['-m','tools.cog03c_capacity_pilot','--quick','--out',str(OUT/'capacity.json')])
    r=json.loads((OUT/'capacity.json').read_text(encoding='utf8'))
    if sum(x['n'] for x in r['rows'])!=120 or any(x['bsc_rank_disagreements'] for x in r['rows']):raise RuntimeError('invalid pilot evidence')
    report['source_after']=source_check();report['passed']=True;save()

if __name__=='__main__':main()
