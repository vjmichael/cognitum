"""Source-bound C2A/B research gate. Preserve original B/C acceptance runner.
No new required production dependencies; no optional-skip substitutions.
Full local Linux pilots are evidence only, not replicated by this smoke gate.
"""
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from tools import cog03bc_research_acceptance as prior

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'docs/research/COG03C2_SOURCE_MANIFEST.json'


def source_check():
    sha=prior.source_check()
    m=json.loads(MANIFEST.read_text(encoding='utf8'))
    for p,blob in m['git_blobs'].items():
        if prior.git('rev-parse','HEAD:'+p)!=blob:raise RuntimeError('C2 source drift: '+p)
    return sha


def main():
    before=source_check()
    prior.main()
    xml=prior.OUT/'tests.xml'
    cases=list(ET.parse(xml).iter('testcase'))
    groups={'c2a':sum('test_cog03c2_frontier' in c.attrib.get('classname','') for c in cases),
            'c2b':sum('test_cog03c2b_dynamic' in c.attrib.get('classname','') for c in cases)}
    if len(cases)!=262 or groups!={'c2a':11,'c2b':25}:
        raise RuntimeError('C2 dedicated cohort mismatch: '+repr(groups))
    if any(c.find(tag) is not None for c in cases for tag in ('failure','error','skipped')):raise RuntimeError('C2 required test did not pass')
    after=source_check()
    if before!=after:raise RuntimeError('source changed')
    (prior.OUT/'c2-result.json').write_text(json.dumps({'schema':'cognitum.cog03c2.acceptance.v1','source_sha':before,'source_after':after,'passed':True,'tests_passed':len(cases),'groups':groups,'production_enabled':False,'scope':'bounded reference tests; full Linux budget pilots not rerun here'},indent=2)+'\n',encoding='utf8')

if __name__=='__main__':main()
