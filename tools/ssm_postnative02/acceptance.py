"""POST-NATIVE-02: frozen external scientific references and genuine HDC/KAN negative controls.
Same-head predecessor custody, bounded acceptance; never grants deployment rights.
"""
import argparse
import json
import os
import platform
import sys
from pathlib import Path
from tools.ssm_postnative01.acceptance import (
    PINS, LINEAR, VERIFY, DYNAMICS, EXTENDED, STOCHASTIC, ADVANCED,
    IDENTIFICATION, DISCOVERY, CONTROL, CONTROL_EXTENDED, LEARNED,
    SELECTIVE, SCIENTIFIC, INFERENCE, INTEROP, BASELINE,
    NEW_PINS as PRIOR, git, need, sha, run_tests,
)

NEW_PINS = {
    'cognitum/research/ssm_external_qualification.py':
        '5c15058ce70e9b6cd71c5bbb48cfa1839ce3dc72',
    'research_tests/ssm_postnative02/test_external_science.py':
        '008b9b81e0750c617f879d061468445211555a0e',
    'research_tests/ssm_postnative02/test_uncertainty.py':
        '33b13cae2375f5234784ea662662801624d0c1be',
    'research_tests/ssm_postnative02/test_kan_native.py':
        'b0f3687ef1ad555e3c367f3a1fd277c707d43b93',
    'research_tests/ssm_postnative02/data/misra1a.csv':
        '9abeeedc4cb6d6224e51a8807b25a9462a874232',
    'research_tests/ssm_postnative02/data/norris.csv':
        'aac8b80ae3f056a5ac22293a412eb39765147451',
    '.gitattributes':
        '6384a7476ad722a0675aa4e1eb17e70a88099153',
}

def run(prior, out):
    root=Path(prior).resolve()
    out=Path(out).resolve()
    head=git('rev-parse','HEAD')
    need(not os.getenv('GITHUB_SHA') or os.environ['GITHUB_SHA']==head,'source SHA mismatch')
    need(not git('status','--porcelain','--untracked-files=no'),'tracked drift')
    old=dict(PINS,**LINEAR,**VERIFY,**DYNAMICS,**EXTENDED,**STOCHASTIC,
             **ADVANCED,**IDENTIFICATION,**DISCOVERY,**CONTROL,
             **CONTROL_EXTENDED,**LEARNED,**SELECTIVE,**SCIENTIFIC,
             **INFERENCE,**INTEROP,**BASELINE,**PRIOR)
    pins=dict(old,**NEW_PINS)
    need(len(pins)>=80,'expected cumulative source pins')
    for path,blob in pins.items():
        need(git('rev-parse',head+':'+path)==blob,'source pin '+path)
    raw=(root/'receipt.json').read_bytes()
    prev=json.loads(raw)
    need(prev['source_sha']==head and prev['status']=='PASS'
         and prev['source_pins']==old,'same-head POST-NATIVE-01 evidence')
    need(prev['dedicated']==dict(tests=19,failures=0,errors=0,skipped=0),
         'predecessor test inventory')
    for name,d in prev['artifacts'].items():
        p=(root/name).resolve()
        need(p.is_relative_to(root) and p.is_file() and sha(p.read_bytes())==d,
             'prior artifact digest')
    out.mkdir(parents=True,exist_ok=False)
    dedicated=run_tests(['research_tests/ssm_postnative02'],
                        out/'tests.xml',out/'tests.log',44)
    combined=run_tests(['research_tests/ssm_postnative',
                        'research_tests/ssm_postnative02'],
                        out/'combined.xml',out/'combined.log',63)
    evidence=dict(
        source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,
        prior_postnative01_sha256=sha(raw),source_pins=pins,
        dedicated=dedicated,combined=combined,
        accepted_original_native_391_sha=
            'c382da2ef3e31643c39f7a01acf2aa1098df469a',
        observed_external_measurements=50,
        source_dataset_rights_independently_verified=False,
        NIST_certification_is_not_physical_dynamical_truth=True,
        all_research_scopes_complete=False,
        execution_authorized=False,
        artifacts={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()},
    )
    (out/'receipt.json').write_text(
        json.dumps(evidence,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(dedicated,combined)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--prior',required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    run(a.prior,a.out)
