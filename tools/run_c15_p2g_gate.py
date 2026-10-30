"""Offline, research-only C15 P2G selected-suite runner.

No downloads, network, OS privilege, worker launch or Lu integration.
Exit nonzero if one required selected suite or descriptor check fails.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    ("c15_independent_and_regressions", [sys.executable, "-m", "pytest", "-q", "tests/test_c15*"]),
    ("c13_c14_regressions", [sys.executable, "-m", "pytest", "-q", "tests/test_c13*", "tests/test_c14*"]),
    ("protobuf_descriptors", [sys.executable, "tools/verify_protobuf_schemas.py", "--require"]),
]


def run():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    result = {"research_only": True, "status": "FAILED", "suite_results": []}
    for name, cmd in COMMANDS:
        # Expand globs: subprocess does not invoke a shell by design.
        command = []
        for word in cmd:
            if "*" in word:
                paths = sorted(str(p.relative_to(ROOT)) for p in ROOT.glob(word))
                if not paths:
                    result["suite_results"].append({"name": name, "status": "MISSING_TEST_FILES"})
                    print(json.dumps(result, indent=2))
                    return 2
                command.extend(paths)
            else:
                command.append(word)
        start = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                       text=True, timeout=180, check=False)
            entry = {"name": name, "status": "PASS" if completed.returncode == 0 else "FAIL",
                     "return_code": completed.returncode,
                     "elapsed_s": round(time.monotonic()-start, 3),
                     "output_tail": (completed.stdout + completed.stderr)[-2200:]}
        except subprocess.TimeoutExpired:
            entry = {"name": name, "status": "TIMEOUT", "elapsed_s": round(time.monotonic()-start,3)}
        result["suite_results"].append(entry)
        if entry["status"] != "PASS":
            print(json.dumps(result, indent=2))
            return 1
    result["status"] = "SELECTED_SUITES_PASS_NOT_PRODUCTION_GATE"
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
