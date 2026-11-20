"""Same-head O/P native qualification with provenance and measured resources."""
import argparse,hashlib,json,os,platform,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
from cognitum.research import kan_weak_form as p,kan_function_metrics as o
from tools.cog04p.oracle import verify
from tools.cog04p.fixtures import probe

ROOT=Path(__file__).resolve().parents[2]
O_PINS={'cognitum/research/kan_function_metrics.py':'b55215b30249aafada8342b7d794895af17143bd',
'tools/cog04o/acceptance.py':'56e101a50277f1c3a08f7d426a2063c7dbcc0fc9',
'tools/cog04o/oracle.py':'c48b44d734f1e9336a27fc439362c1778ef9acca',
'tools/cog04o/fixtures.py':'e9b449cb1b569d8c1552a46d525a65b02f116c27',
'research_tests/cog04o/test_function_metrics.py':'327b12f0d239521041365702c4e02b7e1215b4bc'}
def sha(data):return hashlib.sha256(data).hexdigest()
def main(prior,out):
    os.chdir(ROOT);prior=Path(prior).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    p.need(not os.getenv('GITHUB_SHA') or head==os.getenv('GITHUB_SHA'),'wrong source')
    p.need(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'tracked source drift')
    for name,blob in O_PINS.items():
        p.need(subprocess.check_output(['git','rev-parse',head+':'+name],text=True).strip()==blob,'O source pin drift')
    oldraw=(prior/'receipt.json').read_bytes();old=json.loads(oldraw)
    p.need(old['source_sha']==head and old['status']=='PASS' and old['totals']==dict(tests=14,failures=0,errors=0,skipped=0)
           and old['prior_manifest_pins']==1650,'same-head O receipt')
    for name,digest in old['artifacts'].items():
        path=(prior/name).resolve()
        p.need(path.is_relative_to(prior) and path.is_file() and sha(path.read_bytes())==digest,'O artifact drift')
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        res=subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04p','--junitxml',str(xml)],
            env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    p.need(res.returncode==0,'COG-04P tests failed')
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite'))
            for k in ('tests','errors','failures','skipped')}
    p.need(totals==dict(tests=14,errors=0,failures=0,skipped=0),str(totals))
    rows=[]
    for stage in ('J','K','L'):
        left=prior/f'{stage}.left.checkpoint.pb';baseline=prior/f'{stage}.right.checkpoint.pb'
        secondary=out/f'{stage}.probe.checkpoint.pb';secondary.write_bytes(probe(stage))
        (out/f'{stage}.learned.checkpoint.pb').write_bytes(left.read_bytes())
        (out/f'{stage}.baseline.checkpoint.pb').write_bytes(baseline.read_bytes())
        row=dict(stage=stage)
        for kind,right in [('O',baseline),('P',secondary)]:
            target=out/f'{stage}.{kind}.json'
            run=subprocess.run([sys.executable,'-m','tools.cog04p.profile','--kind',kind,'--left',str(left),
                '--right',str(right),'--out',str(target)],env=env,capture_output=True,text=True,timeout=120,check=True)
            measured=json.loads(run.stdout)
            p.need(measured['result_sha256']==sha(target.read_bytes()) and measured['source_left_sha256']==sha(left.read_bytes())
                and measured['source_right_sha256']==sha(right.read_bytes()),'profile source binding')
            p.need(measured['peak_bytes']>=measured['before_peak_bytes']>0 and measured['elapsed_ns']>0 and measured['process_cpu_ns']>0,'missing measurements')
            if kind=='O':
                p.need(target.read_bytes()==(prior/f'{stage}.metrics.json').read_bytes(),'profile O result differs')
            else:
                measured['oracle']=verify((left.read_bytes(),secondary.read_bytes()),target.read_bytes(),measured['spectrum'])
            row[kind]=measured
        rows.append(row)
    report=dict(source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,totals=totals,
        prior_o_sha256=sha(oldraw),o_source_pins=O_PINS,rows=rows,
        qualification='finite represented subspace, spatial gradient on normalized unit box',
        resource_claim='elapsed and CPU operation interval; lifetime peak process RSS/working set includes imports; one sample per stage and kind',
        production_enabled=False,hard_os_quota_claim=False,
        artifacts={f.name:sha(f.read_bytes()) for f in sorted(out.iterdir()) if f.is_file()})
    (out/'receipt.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(totals,'J/K/L exact weak forms, independent Ritz spectra and six isolated process measurements')

if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--prior',required=True);q.add_argument('--out',required=True)
    a=q.parse_args();main(a.prior,a.out)
