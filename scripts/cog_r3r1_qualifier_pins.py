"""CI-only independent input/result pinning for production-lineage SSM Job.

Never an installed issuer, no arbitrary file/provider/operation selection,
never converts numerical output into an authorized Core result.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

# This file is invoked by path from scripts/, which Python places on
# sys.path instead of the Git checkout root. This is a source-only CI helper;
# the protected production child still enters its own pinned source ONLY
# after native token+Job verification.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cognitum.mel.ssm_supervisor import SSMComputeFactory, OP


def _fixed():
    assert sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true"
    base = Path(os.environ["GITHUB_WORKSPACE"]) / "native/windows_scm_production/target"
    assert base.is_absolute() and base.is_dir() and not base.is_symlink()
    return base


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _expected(data):
    request = json.loads(data)
    assert type(request) is dict and set(request) == {"operation", "payload"}
    assert request["operation"] == OP
    actual = SSMComputeFactory().handle(OP, request["payload"])
    return json.dumps({"status": "ok", "reply": actual},
                      sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def probe():
    """Diagnostic-only duplicate of the reference frozen smoke environment.

    This reports only the import symbol/module category (no paths, credentials,
    environment dump, or raw traceback), and never authorizes output.
    """
    import re
    import shutil
    import subprocess
    import tempfile

    base = _fixed()
    runtime = base / "q-runtime-parent/runtime"
    parent = runtime.parent
    child = runtime / "cognitum/mel/ssm_r5_fixed_child.py"
    request = base / "q-io/input.frame"
    with tempfile.TemporaryDirectory(prefix="q-import-probe-", dir=parent) as td:
        root = Path(td)
        source = root / "input.frame"
        output = root / "output.frame"
        shutil.copy2(request, source)
        outcome = subprocess.run(
            [str(runtime / "python.exe"), "-I", "-B",
             str(child), str(source), str(output)],
            cwd=runtime,
            timeout=40,
            env={"SystemRoot": os.environ["SystemRoot"],
                 "TEMP": td, "TMP": td, "WINDIR": os.environ["SystemRoot"]},
            capture_output=True,
            check=False,
        )
    if outcome.returncode == 0:
        print("PASS_FROZEN_SSM_PROBE")
        return
    stderr = outcome.stderr[:8192].decode("utf-8", errors="replace")
    match = re.search(
        r"ImportError: cannot import name ['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]"
        r" from ['\"]([A-Za-z_][A-Za-z0-9_.]*)['\"]", stderr)
    if match:
        print("FROZEN_IMPORT_REFUSED_SYMBOL=" + match.group(1)
              + " MODULE=" + match.group(2))
    else:
        match = re.search(
            r"ModuleNotFoundError: No module named ['\"]([A-Za-z_][A-Za-z0-9_.]*)['\"]",
            stderr)
        if match:
            print("FROZEN_IMPORT_MISSING_MODULE=" + match.group(1))
        elif "DLL load failed" in stderr:
            print("FROZEN_IMPORT_DLL_LOAD_FAILURE")
        else:
            print("FROZEN_IMPORT_OTHER_ERROR")
    raise SystemExit(3)


def prepare():
    base = _fixed()
    runtime = base / "q-runtime-parent/runtime"
    input_file = base / "q-io/input.frame"
    output_file = base / "q-io/output.frame"
    child = runtime / "cognitum/mel/ssm_r5_production_child.py"
    python = runtime / "python.exe"
    assert all(p.is_file() and not p.is_symlink()
               for p in (input_file, child, python))
    assert not output_file.exists()
    expected = _sha(_expected(input_file.read_bytes()))
    env = {
        "COG_PROD_QUAL_PYTHON": str(python),
        "COG_PROD_QUAL_CHILD": str(child),
        "COG_PROD_QUAL_REQUEST": str(input_file),
        "COG_PROD_QUAL_OUTPUT": str(output_file),
        "COG_PROD_QUAL_RESULT_WITNESS": str(base / "q-host/production-qualification.json"),
        "COG_PROD_QUAL_PYTHON_SHA256": _sha(python.read_bytes()),
        "COG_PROD_QUAL_CHILD_SHA256": _sha(child.read_bytes()),
        "COG_PROD_QUAL_REQUEST_SHA256": _sha(input_file.read_bytes()),
        "COG_PROD_QUAL_OUTPUT_SHA256": expected,
    }
    with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as dest:
        for name, value in env.items():
            dest.write(f"{name}={value}\n")
    (base / "q-expected.json").write_text(
        json.dumps({"sha256": expected, "output_authorized": False},
                   sort_keys=True), encoding="ascii")
    print("PASS_QUALIFIER_EXPECTED_MATH_AND_IMAGE_HASHES_PINNED")


def verify():
    base = _fixed()
    actual = (base / "q-io/output.frame").read_bytes()
    request = (base / "q-io/input.frame").read_bytes()
    assert actual == _expected(request)
    record = json.loads(Path("q-scm-receipt.json").read_text(encoding="ascii"))
    stored = json.loads((base / "q-expected.json").read_text(encoding="ascii"))
    assert record["status"] == "PASS_CI_PRODUCTION_LINEAGE_NATIVE_APP_CONTAINER_SSM_JOB"
    assert _sha(actual) == stored["sha256"] == record["output_sha256"]
    assert all(record[key] is False for key in (
        "output_or_ACK_authorized", "installed_Core_authorized",
        "production_CNG_signed_receipts", "actual_owner_installed_service_changed"
    ))
    print("PASS_REAL_SCM_APP_CONTAINER_SSM_INDEPENDENT_NUMERICS_CI_ONLY")


if __name__ == "__main__":
    if sys.argv[1:] == ["prepare"]:
        prepare()
    elif sys.argv[1:] == ["verify"]:
        verify()
    elif sys.argv[1:] == ["probe"]:
        probe()
    else:
        raise SystemExit(2)
