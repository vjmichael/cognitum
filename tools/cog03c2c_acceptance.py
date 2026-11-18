"""Exact-source C2C gate, preserving all prior research tests. The optional
explicit hosted Linux dataset gate performs pinned acquisition, not a local
claim of author replication. No production dependencies or network at import.
"""
import hashlib, json, os, subprocess, sys, tempfile
from xml.etree import ElementTree as ET
from tools import cog03c2_acceptance as c2

ROOT=c2.ROOT
OUT=c2.prior.OUT


def source_check():
    sha=c2.source_check()
    m=json.loads((ROOT/'docs/research/COG03C2C_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for p,b in m['git_blobs'].items():
        if c2.prior.git('rev-parse','HEAD:'+p)!=b:raise RuntimeError('C2C source drift: '+p)
    return sha


def dataset_gate():
    if os.environ.get('COG03C2C_DATASETS')!='1':return {'status':'not requested for this platform'}
    entries=[]
    with tempfile.TemporaryDirectory(prefix='cog03c2c-') as td:
        for ds in ('promoter','mutag'):
            pair=[]
            for arm in ('resident','streamed'):
                out=OUT/f'c2c-{ds}-{arm}.json'
                log=OUT/f'c2c-{ds}-{arm}.log'
                args=[sys.executable,'-m','tools.cog03c2c_pilot','--data',td,'--acquire','--dataset',ds,'--arm',arm,'--dimension','512','--payload-cap','524288','--address-limit-mib','512','--out',str(out)]
                if ds=='mutag':args+=['--grouped']
                with log.open('wb') as f:subprocess.run(args,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
                row=json.loads(out.read_text(encoding='utf8'));pair.append(row)
                entries.append({'dataset':ds,'arm':arm,'result_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()})
            a,b=pair
            if a['predictions']!=b['predictions'] or a['split_sha256']!=b['split_sha256'] or a['dimension']!=b['dimension'] or b['serialized_snapshot_bytes']>=a['serialized_snapshot_bytes']:raise RuntimeError('dataset replay or storage comparison failed: '+ds)
            if ds=='mutag' and any(x['identical_feature_test_rows'] for x in pair):raise RuntimeError('MUTAG duplicate leakage')
    return {'status':'passed','entries':entries,'scope':'one pinned split per dataset; equal dimension and serialized budget; no performance threshold'}


def main():
    before=source_check();c2.prior.main()
    cases=list(ET.parse(OUT/'tests.xml').iter('testcase'))
    groups={name:sum(test in c.attrib.get('classname','') for c in cases) for name,test in [('c2a','test_cog03c2_frontier'),('c2b','test_cog03c2b_dynamic'),('c2c','test_cog03c2c_structured')]}
    if len(cases)!=288 or groups!={'c2a':11,'c2b':25,'c2c':26}:raise RuntimeError('C2C cohort mismatch '+repr(groups))
    if any(c.find(tag) is not None for c in cases for tag in ('failure','error','skipped')):raise RuntimeError('required test did not pass')
    datasets=dataset_gate();after=source_check()
    if before!=after:raise RuntimeError('source changed')
    (OUT/'c2c-result.json').write_text(json.dumps({'schema':'cognitum.cog03c2c.acceptance.v1','source_sha':before,'source_after':after,'passed':True,'tests_passed':len(cases),'groups':groups,'datasets':datasets,'production_enabled':False},indent=2)+'\n',encoding='utf8')

if __name__=='__main__':main()
