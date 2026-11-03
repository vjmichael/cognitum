#!/usr/bin/env python3
"""CH39 read-only public evidence audit, Windows/Linux, no PowerShell stderr bugs.

No network, install, production modifications or private keys. Python >= 3.9.
Uses the accepted CH39 package + pinned standalone auditor unchanged.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback
import zipfile

ARCHIVE_NAME = 'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
EXPECTED_PACKAGE = '9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
EXPECTED_ENTRIES = 1099
EXPECTED_CASES = 15

class AuditBlocked(Exception):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def write_json(path: Path, content: dict):
    path.write_text(json.dumps(content, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def run_child(cmd: list[str], log: Path, timeout: int = 1200) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors='replace', timeout=timeout)
        log.write_text('COMMAND: ' + cmd[0] + ' [args withheld]\n'
                       + 'EXIT: ' + str(r.returncode) + '\n'
                       + '--- STDOUT ---\n' + r.stdout
                       + '\n--- STDERR ---\n' + r.stderr, encoding='utf-8')
        return r.returncode, r.stdout, r.stderr
    except Exception:
        err = traceback.format_exc()
        log.write_text('Child process did not complete:\n' + err, encoding='utf-8')
        return 1, '', err


def print_status(message: str):
    print(message, flush=True)


def diagnostic(text: str, limit: int = 500) -> str:
    # Last line generally describes Python import/DLL failure better than traceback header.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return (lines[-1] if lines else 'No diagnostic text returned')[:limit]


def main():
    parser = argparse.ArgumentParser(description='CH39 offline Windows test runner v2')
    parser.add_argument('-MathProbe', '--MathProbe', action='store_true', dest='math_probe')
    parser.add_argument('-MpfrDll', '--MpfrDll', default='', dest='mpfr_dll')
    parser.add_argument('--Package', default='')
    parser.add_argument('--ResultsDirectory', default='')
    opts = parser.parse_args()
    directory = Path(__file__).resolve().parent
    package = Path(opts.Package) if opts.Package else directory / ARCHIVE_NAME
    if opts.ResultsDirectory:
        results = Path(opts.ResultsDirectory)
    else:
        label = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
        results = directory / ('CH39_Windows_Results_' + label)
        suffix = 1
        while results.exists():
            results = directory / ('CH39_Windows_Results_' + label + f'_{suffix}')
            suffix += 1
    results.mkdir(parents=True, exist_ok=False)
    summary_file = results / 'CH39_windows_summary.json'
    report = {
        'kit_version': 'Windows Test Kit v2.1 (direct Python)',
        'test': 'CH39 offline public witness and integrity, optional 7-node MPFR probe',
        'time_local': dt.datetime.now().astimezone().isoformat(),
        'platform': sys.platform,
        'python_version': sys.version.split()[0],
        'python_executable': sys.executable,
        'package_sha256': 'NOT_RUN',
        'manifest': 'NOT_RUN',
        'public_signatures': 'NOT_RUN',
        'math_probe': 'NOT_REQUESTED',
        'overall': 'NOT_RUN',
        'scope': 'Read-only public audit; no Linux 5-UID acceptance, signer issuance, or global-optimality proof',
    }
    outcome = 1
    try:
        print_status('CH39 Windows public verification v2 (read-only)')
        print_status('This does not test Linux UID separation or prove global optimality.')
        if sys.version_info < (3, 9):
            raise AuditBlocked('Python 3.9 or newer is required; this is ' + sys.version.split()[0])
        if not package.is_file():
            raise AuditBlocked('Original CH39 package is missing from extracted test kit: ' + package.name)
        actual = sha256(package)
        if actual != EXPECTED_PACKAGE:
            report['package_sha256'] = 'FAIL'
            raise ValueError('CH39 package SHA-256 mismatch; expected ' + EXPECTED_PACKAGE + ' got ' + actual)
        report['package_sha256'] = 'PASS'
        print_status('PASS: original CH39 package SHA-256 matches external pin.')
        try:
            crypto = importlib.import_module('cryptography')
            importlib.import_module('cryptography.hazmat.primitives.asymmetric.ed25519')
            report['cryptography_version'] = crypto.__version__
        except Exception as err:
            (results / 'CH39_dependency_check.log').write_text(traceback.format_exc(), encoding='utf-8')
            raise AuditBlocked('Python cryptography/Ed25519 import failed: '
                               + type(err).__name__ + ': ' + str(err)
                               + '. See CH39_dependency_check.log. To install manually: '
                               + 'py -3 -m pip install --user cryptography') from err
        # Archive SHA-256 is pinned before any content is written. Run Python extraction,
        # not .NET Framework ZipFile.ExtractToDirectory (which has legacy Windows quirks).
        with tempfile.TemporaryDirectory(prefix='CH39_') as temporary:
            root = Path(temporary)
            with zipfile.ZipFile(package, 'r') as archive:
                all_names = archive.namelist()
                if len(all_names) != len(set(all_names)):
                    raise ValueError('Duplicate archive member names')
                # Duplicate and traversal defense even for an already pinned archive.
                audit_module = importlib.import_module('ch39_windows_audit')
                if any(not audit_module.is_safe_name(name) for name in all_names):
                    raise ValueError('Unsafe archive member name')
                archive.extractall(root)
            audit_file = results / 'CH39_public_audit.json'
            audit_log = results / 'CH39_public_audit.log'
            rc, out, err = run_child([
                sys.executable, str(directory / 'ch39_windows_audit.py'),
                '--package', str(package), '--root', str(root), '--output', str(audit_file)
            ], audit_log)
            if rc != 0:
                desc = diagnostic(err or out)
                if audit_file.is_file():
                    try: desc = str(json.loads(audit_file.read_text(encoding='utf-8')).get('error', desc))
                    except Exception: pass
                raise ValueError('Public audit failed: ' + desc + '. Details: ' + audit_log.name)
            if not audit_file.is_file():
                raise ValueError('Auditor exited 0 without writing its JSON result')
            audit = json.loads(audit_file.read_text(encoding='utf-8'))
            p = audit.get('package', {})
            w = audit.get('public_witness', {})
            if (audit.get('status') != 'PASS'
                or p.get('manifest_sha256_verified_files') != EXPECTED_ENTRIES
                or w.get('signed_cases') != EXPECTED_CASES
                or w.get('original_case_pins_matched') != EXPECTED_CASES
                or w.get('attestor_signatures_verified') != EXPECTED_CASES
                or w.get('final_signer_signatures_verified') != EXPECTED_CASES
                or w.get('terminal_witness_tip') != '112980038c992461c0eaf43c2d3f066191e4c7404b058ba434c1ba1352af68c5'):
                raise ValueError('Public audit returned unexpected counts, status, or trust pin')
            report['manifest'] = 'PASS_1099_FILES'
            report['public_signatures'] = 'PASS_15_ATTESTOR_15_SIGNER'
            report['overall'] = 'PASS_PUBLIC_WINDOWS_AUDIT'
            print_status('PASS: all 1,099 archived file hashes verified.')
            print_status('PASS: 15 original case pins, 30 Ed25519 signatures and pinned witness tip.')
            outcome = 0
            if opts.math_probe:
                math_file = results / 'CH39_mpfr_probe.json'
                math_log = results / 'CH39_mpfr_probe.log'
                cmd = [sys.executable, str(directory / 'ch39_mpfr_probe.py'),
                       '--root', str(root), '--output', str(math_file)]
                if opts.mpfr_dll:
                    cmd.extend(['--mpfr-dll', opts.mpfr_dll])
                mrc, stdout, stderr = run_child(cmd, math_log)
                if math_file.exists():
                    try: report['math_probe'] = json.loads(math_file.read_text(encoding='utf-8'))['status']
                    except Exception: report['math_probe'] = 'FAIL_MALFORMED_RESULT'
                else:
                    report['math_probe'] = 'FAIL_NO_RESULT'
                if mrc == 0 and report['math_probe'] == 'PASS':
                    print_status('PASS: optional 224-bit MPFR seven-node compatibility probe.')
                elif report['math_probe'] == 'BLOCKED' or mrc == 2:
                    report['overall'] = 'PASS_PUBLIC_MATH_BLOCKED'
                    print_status('BLOCKED: optional MPFR probe; public signature audit PASSED. See probe log.')
                    outcome = 2
                else:
                    report['overall'] = 'PASS_PUBLIC_MATH_FAILED'
                    print_status('FAIL: optional MPFR probe; public signature audit PASSED. See probe log.')
                    outcome = 1
    except AuditBlocked as err:
        report['overall'] = 'BLOCKED_PREREQUISITE'
        report['reason'] = str(err)
        print_status('BLOCKED: ' + str(err))
        outcome = 2
    except Exception as err:
        report['overall'] = 'FAIL'
        report['error'] = type(err).__name__ + ': ' + str(err)
        (results / 'CH39_windows_runner_error.log').write_text(traceback.format_exc(), encoding='utf-8')
        print_status('FAIL: ' + report['error'])
        print_status('See CH39_windows_runner_error.log for the full traceback.')
        outcome = 1
    finally:
        report['exit_code'] = outcome
        write_json(summary_file, report)
        print_status('Summary: ' + str(summary_file))
        print_status('Share JSON/log files if a test is BLOCKED or FAIL; do not include machine keys.')
    return outcome

if __name__ == '__main__':
    raise SystemExit(main())
