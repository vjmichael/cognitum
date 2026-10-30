"""Operator-run Windows x86-64 disposable-VM smoke, NOT Lu/OS isolation proof.

No install, network, registry, VM shutdown, privileged API or Lu dependency.
Only writes run evidence to operator-provided output directory. Each pytest
suite runs as a separate Python child process with a finite timeout.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

GATE_NAMES = [
    'tests/test_c15_t4_p11_p12_boundary.py',
    'tests/test_c15_t4_p8_p10_external_readiness.py',
    'tests/test_c15_t4_p5_p7_assurance.py',
    'tests/test_c15_t4_p4_evidence_gate.py',
]
# Operational version guard for this reference test kit, NOT a full transitive
# hash lock or Windows wheel certification.
PINNED = {
    'protobuf': '6.33.6',
    'cryptography': '46.0.4',
    'asn1crypto': '1.5.1',
    'pytest': '9.0.2',
}


def platform_eligible(system: str, machine: str) -> bool:
    return system.lower() == 'windows' and machine.lower() in ('amd64','x86_64')


def runtime_preflight() -> dict:
    system=platform.system()
    machine=platform.machine()
    packages={}
    for key in PINNED:
        try: packages[key] = importlib.metadata.version(key)
        except importlib.metadata.PackageNotFoundError: packages[key] = None
    openssl=shutil.which('openssl')
    try:
        version=subprocess.run([openssl,'version'],capture_output=True,timeout=5,
                               check=False).stdout.decode('utf-8','replace').strip() if openssl else None
    except (OSError,subprocess.TimeoutExpired):version=None
    root=Path(__file__).resolve().parents[1]
    return {'platform':system, 'machine':machine,'python':platform.python_version(),
            'python_executable':str(Path(sys.executable).resolve()),
            'openssl_executable':openssl,'openssl_version':version,
            'package_versions':packages,'root':str(root),
            'windows_x86_64_eligible':platform_eligible(system,machine),
            'pinned_direct_dependencies_match':all(packages[k]==v for k,v in PINNED.items()),
            'test_modules_present':all((root/n).is_file() for n in GATE_NAMES)}


def execute(*,output_directory:Path) -> dict:
    preflight=runtime_preflight()
    if not preflight['windows_x86_64_eligible']:
        raise RuntimeError('P13_WINDOWS_ONLY: never report Linux as native Windows pass')
    if not preflight['pinned_direct_dependencies_match'] or not preflight['test_modules_present']:
        raise RuntimeError('P13_PINNED_ENVIRONMENT_OR_TESTS_MISSING')
    if not preflight['openssl_executable']:
        raise RuntimeError('P13_OPENSSL_BINARY_MISSING')
    if output_directory.exists() and any(output_directory.iterdir()):
        raise RuntimeError('P13_OUTPUT_DIR_MUST_BE_EMPTY: no evidence overwrite')
    output_directory.mkdir(parents=True,exist_ok=True)
    root=Path(preflight['root'])
    env={**os.environ,'PYTHONPATH':str(root),'PYTHONNOUSERSITE':'1',
         'PYTHONDONTWRITEBYTECODE':'1'}
    details=[]
    for index,module in enumerate(GATE_NAMES,1):
        try:
            p=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider',module],
                             cwd=root,env=env,capture_output=True,text=True,errors='replace',
                             timeout=180,check=False,shell=False)
            stdout,stderr,return_code=p.stdout,p.stderr,p.returncode
        except subprocess.TimeoutExpired:
            stdout,stderr,return_code='','P13_SUITE_TIMEOUT',124
        (output_directory/f'suite-{index}.stdout.txt').write_text(stdout,encoding='utf-8')
        (output_directory/f'suite-{index}.stderr.txt').write_text(stderr,encoding='utf-8')
        details.append({'test_module':module,'return_code':return_code,
                        'stdout_sha256':hashlib.sha256(stdout.encode()).hexdigest(),
                        'stderr_sha256':hashlib.sha256(stderr.encode()).hexdigest()})
    passed=all(d['return_code']==0 for d in details)
    report={'schema_version':1,'gate':'C15-T4-P13-WINDOWS-PORTABLE-TEST-EXECUTION',
            'created_utc':datetime.now(timezone.utc).isoformat(),
            'environment':preflight,'suite_results':details,
            'windows_native_tests_passed':passed,
            'windows_os_sandbox_verified':False,'lu_integration_verified':False,
            'independent_timestamp_authority_verified':False,
            'real_physical_data_verified':False,'research_only':True,'grants_authority':False}
    (output_directory/'gate-result.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return report


def main() -> int:
    parser=argparse.ArgumentParser(description='Disposable Windows x86-64 P13 test gate')
    parser.add_argument('--output',required=True,type=Path)
    opts=parser.parse_args()
    try:
        result=execute(output_directory=opts.output.resolve())
    except Exception as exc:
        print(f'P13_NOT_VERIFIED: {exc}',file=sys.stderr)
        return 2
    print('P13_TESTS_PASS' if result['windows_native_tests_passed'] else 'P13_TESTS_FAIL')
    print(f'Evidence: {opts.output.resolve()}')
    return 0 if result['windows_native_tests_passed'] else 1


if __name__=='__main__':raise SystemExit(main())
