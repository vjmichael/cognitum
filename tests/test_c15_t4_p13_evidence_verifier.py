"""P13 offline verifier tests: all fixtures are fabricated, NOT Windows evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.verify_c15_t4_p13_windows_evidence import inspect, EvidenceRejected, EXPECTED_MODULES, PINNED


def fixture(tmp_path):
    env = {"platform": "Windows", "machine": "AMD64", "python": "3.11.9",
           "python_executable": "C:\\Python311\\python.exe",
           "openssl_executable": "C:\\Tools\\openssl.exe", "openssl_version": "OpenSSL 3.3.4 11 Feb 2025",
           "package_versions": dict(PINNED), "windows_x86_64_eligible": True,
           "pinned_direct_dependencies_match": True, "test_modules_present": True}
    suites=[]
    for i, mod in enumerate(EXPECTED_MODULES, 1):
        stdout=f"suite {i}\n1 passed in 0.1s\n"
        stderr=""
        (tmp_path / f"suite-{i}.stdout.txt").write_text(stdout,encoding="utf-8")
        (tmp_path / f"suite-{i}.stderr.txt").write_text(stderr,encoding="utf-8")
        suites.append({"test_module":mod,"return_code":0,
                       "stdout_sha256":hashlib.sha256(stdout.encode()).hexdigest(),
                       "stderr_sha256":hashlib.sha256(stderr.encode()).hexdigest()})
    payload={"schema_version":1,"gate":"C15-T4-P13-WINDOWS-PORTABLE-TEST-EXECUTION",
             "environment":env,"suite_results":suites,"windows_native_tests_passed":True,
             "windows_os_sandbox_verified":False,"lu_integration_verified":False,
             "independent_timestamp_authority_verified":False,"real_physical_data_verified":False,
             "research_only":True,"grants_authority":False}
    (tmp_path / "gate-result.json").write_text(json.dumps(payload),encoding="utf-8")
    return payload


def save(p, d):
    (d / "gate-result.json").write_text(json.dumps(p),encoding="utf-8")


def test_good_synthetic_is_unattested(tmp_path):
    fixture(tmp_path)
    out=inspect(tmp_path)
    assert out["verdict"] == "INTERNALLY_CONSISTENT_UNATTESTED"
    assert out["native_windows_execution_authenticated"] is False
    assert out["log_files_verified"] == 8


def test_crlf_on_disk_is_tolerated(tmp_path):
    fixture(tmp_path)
    path=tmp_path/'suite-1.stdout.txt'
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert inspect(tmp_path)["suite_count"] == 4

@pytest.mark.parametrize('field,value',[
    ('gate','OTHER_GATE'), ('windows_native_tests_passed',False),
    ('research_only',False), ('grants_authority',True),
    ('windows_os_sandbox_verified',True), ('lu_integration_verified',True),
    ('independent_timestamp_authority_verified',True), ('real_physical_data_verified',True)])
def test_reject_wrong_metadata(tmp_path,field,value):
    p=fixture(tmp_path);p[field]=value;save(p,tmp_path)
    with pytest.raises(EvidenceRejected):inspect(tmp_path)

@pytest.mark.parametrize('field,value',[
    ('platform','Linux'), ('machine','arm64'), ('python','3.12.0'),
    ('windows_x86_64_eligible',False), ('pinned_direct_dependencies_match',False),
    ('test_modules_present',False), ('openssl_version','LibreSSL 3.0')])
def test_reject_wrong_env(tmp_path,field,value):
    p=fixture(tmp_path);p['environment'][field]=value;save(p,tmp_path)
    with pytest.raises(EvidenceRejected):inspect(tmp_path)


def test_reject_dependency_change(tmp_path):
    p=fixture(tmp_path);p['environment']['package_versions']['pytest']='0';save(p,tmp_path)
    with pytest.raises(EvidenceRejected):inspect(tmp_path)


def test_reject_tampered_log(tmp_path):
    fixture(tmp_path)
    path=tmp_path/'suite-3.stdout.txt'
    path.write_text(path.read_text()+'tampered')
    with pytest.raises(EvidenceRejected,match='LOG_DIGEST_MISMATCH'):inspect(tmp_path)


def test_reject_missing_log(tmp_path):
    fixture(tmp_path);(tmp_path/'suite-2.stderr.txt').unlink()
    with pytest.raises(EvidenceRejected):inspect(tmp_path)


def test_reject_duplicate_modules(tmp_path):
    p=fixture(tmp_path);p['suite_results'][3]['test_module']=p['suite_results'][2]['test_module'];save(p,tmp_path)
    with pytest.raises(EvidenceRejected):inspect(tmp_path)


def test_reject_extra_module(tmp_path):
    p=fixture(tmp_path);p['suite_results'].append(p['suite_results'][0]);save(p,tmp_path)
    with pytest.raises(EvidenceRejected):inspect(tmp_path)


def test_reject_failed_process(tmp_path):
    p=fixture(tmp_path);p['suite_results'][0]['return_code']=124;save(p,tmp_path)
    with pytest.raises(EvidenceRejected):inspect(tmp_path)


def test_reject_duplicate_json_keys(tmp_path):
    fixture(tmp_path)
    path=tmp_path/'gate-result.json'
    text=path.read_text()
    path.write_text(text.replace('"schema_version": 1','"schema_version": 1, "schema_version": 1'))
    with pytest.raises(EvidenceRejected,match='DUPLICATE_JSON_KEY'):inspect(tmp_path)


def test_reject_nan(tmp_path):
    fixture(tmp_path)
    path=tmp_path/'gate-result.json'
    path.write_text(path.read_text().replace('"schema_version": 1','"schema_version": NaN'))
    with pytest.raises(EvidenceRejected,match='NONFINITE_JSON_CONSTANT'):inspect(tmp_path)


def test_reject_symlink_log(tmp_path):
    fixture(tmp_path)
    path=tmp_path/'suite-1.stdout.txt';other=tmp_path/'else.txt'
    other.write_bytes(path.read_bytes());path.unlink();path.symlink_to(other)
    with pytest.raises(EvidenceRejected):inspect(tmp_path)


def test_reject_oversized_log(tmp_path):
    fixture(tmp_path)
    path=tmp_path/'suite-1.stdout.txt'
    path.write_bytes(b'A' * (2*1024*1024 + 1))
    with pytest.raises(EvidenceRejected):inspect(tmp_path)


def test_reject_no_positive_test_summary_even_if_hash_updated(tmp_path):
    p=fixture(tmp_path)
    path=tmp_path/'suite-1.stdout.txt'
    path.write_text('no tests ran\n')
    p['suite_results'][0]['stdout_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    save(p,tmp_path)
    with pytest.raises(EvidenceRejected,match='NO_POSITIVE_PYTEST_SUMMARY'):inspect(tmp_path)
