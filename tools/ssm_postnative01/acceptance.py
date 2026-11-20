"""Post-native residual-check acceptance; inherit scoped 391-case source receipts."""
import argparse
import json
import os
import platform
import sys
from pathlib import Path

from tools.ssm09b.acceptance import (
    PINS, LINEAR, VERIFY, DYNAMICS, EXTENDED, STOCHASTIC, ADVANCED,
    IDENTIFICATION, DISCOVERY, CONTROL, CONTROL_EXTENDED, LEARNED,
    SELECTIVE, SCIENTIFIC, INFERENCE, INTEROP, NEW_PINS as BASELINE,
    git, need, sha, run_tests,
)

NEW_PINS = {
    'research_tests/ssm_postnative/test_residual_controls.py':
        '15046a2e53721b34ef2be2215d1680e18539e464',
}


def run(prior, out):
    root = Path(prior).resolve()
    out = Path(out).resolve()
    head = git('rev-parse', 'HEAD')
    need(not os.getenv('GITHUB_SHA') or os.environ['GITHUB_SHA'] == head,
         'source SHA mismatch')
    need(not git('status', '--porcelain', '--untracked-files=no'),
         'tracked source drift')
    previous = dict(
        PINS, **LINEAR, **VERIFY, **DYNAMICS, **EXTENDED,
        **STOCHASTIC, **ADVANCED, **IDENTIFICATION, **DISCOVERY,
        **CONTROL, **CONTROL_EXTENDED, **LEARNED, **SELECTIVE,
        **SCIENTIFIC, **INFERENCE, **INTEROP, **BASELINE,
    )
    current = dict(previous, **NEW_PINS)
    for path, blob in current.items():
        need(git('rev-parse', head + ':' + path) == blob,
             'source pin ' + path)
    raw = (root / 'receipt.json').read_bytes()
    prior_receipt = json.loads(raw)
    need(prior_receipt['source_sha'] == head and
         prior_receipt['status'] == 'PASS' and
         prior_receipt['source_pins'] == previous,
         'same-head SSM-09B scoped native receipt')
    need(prior_receipt['dedicated'] ==
         dict(tests=37, failures=0, errors=0, skipped=0),
         'SSM-09B dedicated inventory')
    need(prior_receipt['consolidated'] ==
         dict(tests=391, failures=0, errors=0, skipped=0),
         'SSM-09B consolidated inventory')
    for name, expected_sha in prior_receipt['artifacts'].items():
        p = (root / name).resolve()
        need(p.is_relative_to(root) and p.is_file() and
             sha(p.read_bytes()) == expected_sha,
             'prior artifact digest mismatch')
    out.mkdir(parents=True, exist_ok=False)
    result = run_tests(['research_tests/ssm_postnative'],
                       out / 'tests.xml', out / 'tests.log', 19)
    record = dict(
        source_sha=head,
        status='PASS',
        platform=platform.platform(),
        python=sys.version,
        prior_ssm09b_sha256=sha(raw),
        source_pins=current,
        dedicated=result,
        original_scoped_native_qualification_sha=
            'c382da2ef3e31643c39f7a01acf2aa1098df469a',
        inherited_scoped_acceptance=391,
        broader_ds_capabilities_accepted=0,
        all_research_scopes_complete=False,
        execution_authorized=False,
        artifacts={p.name:sha(p.read_bytes())
                   for p in sorted(out.iterdir()) if p.is_file()},
    )
    (out / 'receipt.json').write_text(
        json.dumps(record, indent=2, allow_nan=False) + '\n',
        encoding='utf-8')
    print(result)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--prior',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    run(args.prior,args.out)
