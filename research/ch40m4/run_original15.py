"""CH40-M.4: fail-closed, offline, native IBEX validation on 15 original CH40-E traces.

Usage:
python research/ch40m4/run_original15.py \
  --archive /path/Cognitum_CH_C14_40_E_Actual_MPFR_Producer_Traces_2026-11-03.zip \
  --ibexsolve /path/to/ibexsolve --ibex-point /path/to/ibex_point \
  --out /path/to/isolated/results

A parser PASS and point interval intersection are NOT global optimality proofs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import zipfile
from fractions import Fraction
from types import SimpleNamespace

EXPECTED_ARCHIVE = "6dfd4ea081b783503c7d960419766296642da68a246033fdcf0da94282882078"
EXPECTED_CH39 = "9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b"
CH39_NAME = "Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip"
CASE_SUFFIX = "_1_original_mpfr_trace.json"

# Reuse the already-reviewed exact original expression serializer.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ch40m2" / "source"))
from ibex_model import ibex_text  # noqa: E402


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (1_400_000_000, 1_400_000_000))
    resource.setrlimit(resource.RLIMIT_CPU, (6, 6))


def run(command: list[str], wall_seconds: int = 7):
    return subprocess.run(command, capture_output=True, text=True, timeout=wall_seconds,
                          preexec_fn=limits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", type=Path, required=True)
    ap.add_argument("--ibexsolve", type=Path, required=True)
    ap.add_argument("--ibex-point", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if sys.platform != "linux":
        raise SystemExit("Research harness requires Linux resource limits")
    if not all(p.is_file() for p in [args.archive, args.ibexsolve, args.ibex_point]):
        raise SystemExit("Required immutable archive or native executable missing")
    if sha(args.archive.read_bytes()) != EXPECTED_ARCHIVE:
        raise SystemExit("REFUSED: original CH40-E archive SHA-256 changed")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "models").mkdir(exist_ok=True)

    # Only import the independently developed rational checker from the pinned ZIP.
    sys.path.insert(0, str(args.archive))
    from rational_kernel40d import point_objective  # noqa: E402

    records = []
    with zipfile.ZipFile(args.archive) as z:
        if sha(z.read(CH39_NAME)) != EXPECTED_CH39:
            raise SystemExit("REFUSED: original CH39 archive SHA-256 changed")
        manifest = json.loads(z.read("CH40E_MANIFEST_SHA256.json"))
        if manifest.get("protocol") != "CH40E-FILE-MANIFEST-V1":
            raise SystemExit("REFUSED: unexpected frozen manifest protocol")
        pins = manifest["file_sha256"]
        names = sorted(n for n in z.namelist()
                       if n.startswith("results/") and n.endswith(CASE_SUFFIX))
        if len(names) != 15:
            raise SystemExit("REFUSED: original 15 traces are incomplete")
        for i, member in enumerate(names, 1):
            raw = z.read(member)
            if sha(raw) != pins.get(member):
                raise SystemExit("REFUSED: original trace hash differs: " + member)
            name = Path(member).name.removesuffix(CASE_SUFFIX)
            obj = json.loads(raw)
            cert = obj["certificate"]
            if (obj["case"] != name or cert["model"]["d"] != 3
                    or len(cert["model"]["rows"]) not in (80, 160)
                    or cert["root_box"] != [["-10", "1"], ["-5", "5"], ["-5", "5"]]):
                raise SystemExit("REFUSED: original model dimension/bounds changed: " + name)
            payload = ibex_text(SimpleNamespace(name=name, certificate=cert, source_sha256=sha(raw)))
            model = args.out / "models" / (name + ".bch")
            model.write_text(payload)
            rec = {"case": name, "trace_sha256": sha(raw), "model_sha256": sha(payload.encode()),
                   "parser": "FAILED_OR_UNTESTED", "point": "FAILED_OR_UNTESTED"}
            records.append(rec)
            try:
                parsed = run([str(args.ibexsolve), "--simpl=0", "-t0.08",
                              "--stop-at-first", str(model)])
                text = parsed.stdout + parsed.stderr
                if parsed.returncode != 0 or "running" not in text or "results written" not in text:
                    raise RuntimeError("Native parser/solver nonzero or no execution evidence")
                rec["parser"] = "PARSED_SOLVER_CAPPED"
                point = [float(x) for x in cert["incumbent"]]
                if not all(math.isfinite(x) for x in point):
                    raise ValueError("Nonfinite frozen point")
                # Preserve original textual coefficient formatting; C++ stod gets same binary64 values.
                native = run([str(args.ibex_point), str(model), *cert["incumbent"]])
                if native.returncode != 0:
                    raise RuntimeError("Native interval evaluator rejected point")
                lo, hi = map(float, native.stdout.split())
                if not all(math.isfinite(x) for x in [lo, hi]) or lo > hi:
                    raise ValueError("Invalid native interval")
                original = point_objective(cert, [Fraction(x) for x in point])
                reference_minimum = (-original.hi, -original.lo)
                if Fraction(lo) > reference_minimum[1] or Fraction(hi) < reference_minimum[0]:
                    raise ValueError("Native point interval disjoint from independent enclosure")
                rec["point"] = "INDEPENDENT_INTERVAL_INTERSECTION"
                rec["native_point_interval"] = [repr(lo), repr(hi)]
            except (TimeoutError, subprocess.TimeoutExpired, RuntimeError, ValueError,
                    ArithmeticError, OverflowError) as exc:
                rec["failure"] = str(exc)[:300]
            report = {"protocol": "CH40M4-ORIGINAL15-REPLAY-V1",
                      "source_archive_sha256": EXPECTED_ARCHIVE,
                      "scientific_release": "NO_GO",
                      "global_optimality_certified": False,
                      "parser_pass": sum(x["parser"] == "PARSED_SOLVER_CAPPED" for x in records),
                      "point_pass": sum(x["point"] == "INDEPENDENT_INTERVAL_INTERSECTION" for x in records),
                      "cases_completed": len(records), "cases": records}
            (args.out / "CH40M4_REPLAY.json").write_text(json.dumps(report, indent=2) + "\n")
            print(f"{i}/15 {name} {rec['parser']} {rec['point']}", flush=True)
    report["complete"] = len(records) == 15
    report["scoped_pass"] = report["complete"] and report["parser_pass"] == 15 and report["point_pass"] == 15
    (args.out / "CH40M4_REPLAY.json").write_text(json.dumps(report, indent=2) + "\n")
    if not report["scoped_pass"]:
        raise SystemExit("REFUSED: native parsing or independent point check incomplete")
    print("CH40-M.4 scoped engineering PASS, scientific NO-GO")


if __name__ == "__main__":
    main()
