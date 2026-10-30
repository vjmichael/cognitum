"""C15 T4 P13 independent offline evidence *consistency* verifier.

Reads untrusted test-runner export only. Never executes included logs or code.
Checks internal consistency; cannot authenticate VM, host, operator or Python tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

EXPECTED_MODULES = (
    "tests/test_c15_t4_p11_p12_boundary.py",
    "tests/test_c15_t4_p8_p10_external_readiness.py",
    "tests/test_c15_t4_p5_p7_assurance.py",
    "tests/test_c15_t4_p4_evidence_gate.py",
)
PINNED = {
    "protobuf": "6.33.6",
    "cryptography": "46.0.4",
    "asn1crypto": "1.5.1",
    "pytest": "9.0.2",
}
MAX_JSON_BYTES = 256 * 1024
MAX_LOG_BYTES = 2 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class EvidenceRejected(ValueError):
    """Evidence is missing, corrupted, or has contradictory assertions."""


def _unique_pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise EvidenceRejected("DUPLICATE_JSON_KEY")
        result[k] = v
    return result


def _no_constant(value):
    raise EvidenceRejected("NONFINITE_JSON_CONSTANT")


def _data(path: Path, limit: int) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise EvidenceRejected(f"MISSING_OR_SYMLINK_FILE:{path.name}")
    if path.stat().st_size > limit:
        raise EvidenceRejected(f"OVERSIZED_FILE:{path.name}")
    return path.read_bytes()


def _string(v):
    return isinstance(v, str) and bool(v)


def inspect(directory: Path) -> dict:
    """Recompute captured log hashes and validate the reporter's invariants.

    Synthetic files can pass; no trust statement about machine execution follows.
    """
    try:
        directory = Path(directory)
        if not directory.is_dir() or directory.is_symlink():
            raise EvidenceRejected("INVALID_EVIDENCE_DIRECTORY")
        payload = json.loads(_data(directory / "gate-result.json", MAX_JSON_BYTES),
                             object_pairs_hook=_unique_pairs,
                             parse_constant=_no_constant)
        if not isinstance(payload, dict) or payload.get("schema_version") != 1 or type(payload.get("schema_version")) is not int:
            raise EvidenceRejected("INVALID_SCHEMA")
        if payload.get("gate") != "C15-T4-P13-WINDOWS-PORTABLE-TEST-EXECUTION":
            raise EvidenceRejected("WRONG_GATE")
        if payload.get("research_only") is not True or payload.get("grants_authority") is not False:
            raise EvidenceRejected("UNAUTHORIZED_PROMOTION")
        for key in ("windows_os_sandbox_verified", "lu_integration_verified",
                    "independent_timestamp_authority_verified", "real_physical_data_verified"):
            if payload.get(key) is not False:
                raise EvidenceRejected("UNSUPPORTED_ASSURANCE:" + key)
        e = payload.get("environment")
        if not isinstance(e, dict):
            raise EvidenceRejected("INVALID_ENVIRONMENT")
        if e.get("platform") != "Windows" or str(e.get("machine", "")).lower() not in ("amd64", "x86_64"):
            raise EvidenceRejected("WRONG_PLATFORM_CLAIM")
        if e.get("windows_x86_64_eligible") is not True:
            raise EvidenceRejected("INELIGIBLE_PLATFORM")
        if e.get("pinned_direct_dependencies_match") is not True or e.get("test_modules_present") is not True:
            raise EvidenceRejected("MISSING_PINNED_DEPENDENCIES_OR_TESTS")
        if e.get("package_versions") != PINNED:
            raise EvidenceRejected("DEPENDENCY_VERSION_MISMATCH")
        if not _string(e.get("openssl_version")) or not e["openssl_version"].startswith("OpenSSL 3."):
            raise EvidenceRejected("INVALID_OPENSSL_CLAIM")
        if not _string(e.get("openssl_executable")) or not _string(e.get("python_executable")):
            raise EvidenceRejected("MISSING_EXECUTABLE_CLAIMS")
        if e.get("python") is None or not re.fullmatch(r"3\.(?:11|13)\.\d+", str(e["python"])):
            raise EvidenceRejected("UNSUPPORTED_PYTHON_CLAIM")
        details = payload.get("suite_results")
        if not isinstance(details, list) or len(details) != len(EXPECTED_MODULES):
            raise EvidenceRejected("MISSING_OR_EXTRA_SUITES")
        if payload.get("windows_native_tests_passed") is not True:
            raise EvidenceRejected("RUNNER_DID_NOT_PASS")
        digest_report = []
        for ix, (expected, item) in enumerate(zip(EXPECTED_MODULES, details), 1):
            if not isinstance(item, dict) or item.get("test_module") != expected:
                raise EvidenceRejected("SUITE_ID_OR_ORDER_MISMATCH")
            if type(item.get("return_code")) is not int or item["return_code"] != 0:
                raise EvidenceRejected("SUITE_RETURN_CODE_NOT_PASS")
            for stream in ("stdout", "stderr"):
                claimed_hash = item.get(stream + "_sha256")
                if not isinstance(claimed_hash, str) or not SHA256.fullmatch(claimed_hash):
                    raise EvidenceRejected("INVALID_LOG_DIGEST")
                source = _data(directory / f"suite-{ix}.{stream}.txt", MAX_LOG_BYTES)
                try:
                    # Python subprocess.run(text=True) and Path.read_text() both
                    # normalize Windows CRLF; tolerate conversion on write.
                    content = source.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise EvidenceRejected("INVALID_UTF8_LOG") from exc
                normalized = content.replace("\r\n", "\n").replace("\r", "\n")
                digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                if digest != claimed_hash:
                    raise EvidenceRejected("LOG_DIGEST_MISMATCH:" + str(ix) + ":" + stream)
                if stream == "stdout":
                    # A zero exit code is only a reporter claim; require a
                    # non-empty, conventional pytest pass summary as well.
                    match = re.search(r"(?<!\d)(\d+) passed(?:[, ]| in )", normalized)
                    if match is None or int(match.group(1)) < 1:
                        raise EvidenceRejected("NO_POSITIVE_PYTEST_SUMMARY:" + str(ix))
                digest_report.append({"file": f"suite-{ix}.{stream}.txt", "normalized_sha256": digest})
        return {
            "gate": "C15-T4-P13-HOST-EVIDENCE-CONSISTENCY",
            "verdict": "INTERNALLY_CONSISTENT_UNATTESTED",
            "log_files_verified": len(digest_report),
            "suite_count": len(details),
            "logs": digest_report,
            "native_windows_execution_authenticated": False,
            "external_issuer_or_measurement_authenticated": False,
            "windows_os_sandbox_verified": False,
            "research_only": True,
            "grants_authority": False,
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError) as exc:
        raise EvidenceRejected("MALFORMED_OR_INCOMPLETE_EVIDENCE") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline C15 T4 P13 evidence consistency verifier; NOT a platform attestation")
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("--out", type=Path, help="Optional verification report path, outside evidence directory")
    args = parser.parse_args()
    try:
        result = inspect(args.evidence_directory)
    except EvidenceRejected as exc:
        result = {"gate": "C15-T4-P13-HOST-EVIDENCE-CONSISTENCY", "verdict": "REJECTED",
                  "reason": str(exc), "native_windows_execution_authenticated": False,
                  "research_only": True, "grants_authority": False}
    message = json.dumps(result, indent=2, sort_keys=True)
    print(message)
    if args.out is not None:
        target = args.out.resolve()
        if target.exists() or args.evidence_directory.resolve() in target.parents:
            parser.error("Report output must be new and outside the source evidence directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(message + "\n", encoding="utf-8")
    return 0 if result["verdict"] == "INTERNALLY_CONSISTENT_UNATTESTED" else 1

if __name__ == "__main__":
    raise SystemExit(main())
