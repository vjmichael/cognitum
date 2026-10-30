"""Offline Cognitum developer-alpha preflight, NOT an alpha release certificate.

Probes the actual standalone calculator CLI and the default-off registry. It
will not install any plugin, call Lu, mutate user data or grant host authority.
Report output is an observation, not a signed test result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_CAPTURE = 65536


def _run(argv, timeout=15):
    completed = subprocess.run([sys.executable, '-m', 'cognitum', *argv],
                               cwd=ROOT, capture_output=True, timeout=timeout)
    if (completed.returncode != 0 or len(completed.stdout) > MAX_CAPTURE or
            len(completed.stderr) > MAX_CAPTURE):
        return {'passed': False, 'reason': 'CHILD_FAILED_OR_EXCEEDED_BUDGET'}
    try:
        output = json.loads(completed.stdout.decode('utf-8', errors='strict'),
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
    except (ValueError, UnicodeError):
        return {'passed': False, 'reason': 'CHILD_MALFORMED_JSON'}
    if not isinstance(output, dict):
        return {'passed': False, 'reason': 'INVALID_CHILD_OUTPUT_SHAPE'}
    return {'passed': True, 'output': output}


def probe():
    result = {'schema': 1, 'build_kind': 'STANDALONE_DEVELOPER_ALPHA_PREFLIGHT',
              'platform': platform.platform(), 'architecture': platform.machine(),
              'python': platform.python_version(), 'lu_integrated': False,
              'os_worker_isolation_verified': False, 'release_approved': False,
              'independent_evidence_attested': False, 'checks': {}}
    try:
        baseline = _run(['registry'])
        good = baseline['passed'] and baseline['output'].get('plugins') == [] and baseline['output'].get('champions') == {}
        result['checks']['default_registry_disabled'] = bool(good)
    except (OSError, subprocess.TimeoutExpired):
        result['checks']['default_registry_disabled'] = False
    try:
        calc = _run(['--calculator', 'calc', '1/3+1/6'])
        data = calc.get('output', {})
        good = (calc['passed'] and data.get('execution_status') == 'completed'
                and data.get('operation') == 'calc.rational'
                and data.get('result') == {'value': '1/2'}
                and data.get('assurance') == 'exact_arithmetic'
                and data.get('interpretation', {}).get('level') == 'assumption_bound')
        result['checks']['exact_calculator_roundtrip'] = bool(good)
    except (OSError, subprocess.TimeoutExpired):
        result['checks']['exact_calculator_roundtrip'] = False
    result['passed'] = bool(result['checks']) and all(result['checks'].values())
    result['outcome'] = 'PORTABLE_ALPHA_SMOKE_PASS_UNATTESTED' if result['passed'] else 'BLOCKED'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='write a fresh JSON report (never overwrite)')
    args = parser.parse_args(argv)
    report = probe()
    output = (json.dumps(report, sort_keys=True, indent=2) + '\n').encode('utf-8')
    if args.out:
        with args.out.open('xb') as handle:
            handle.write(output)
    else:
        sys.stdout.buffer.write(output)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
