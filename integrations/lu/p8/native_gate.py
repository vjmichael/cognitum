"""C06/P8 opt-in native Lu test gate. Never installs or pushes anything.

Run from an already-disposable local pinned Lu checkout after applying the
versioned Cognitum overlay. This script READS source, runs Cargo tests and
writes a report outside the checkout. It will not fetch, clone or modify GitHub.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

PIN = "bf2334a7d68f72265c37711de9bb5eda1f611d13"
CORE = Path("src-tauri/lu-core")
SOURCE = Path(__file__).resolve().parents[1]
OVERLAY_PATHS = {
    CORE / "src/ansf_memory_gate.rs": SOURCE / "src-tauri/lu-core/src/ansf_memory_gate.rs",
    CORE / "src/ansf_memory_proto.rs": SOURCE / "src-tauri/lu-core/src/ansf_memory_proto.rs",
    CORE / "proto/cognitum/memory/v1/evidence.proto": SOURCE / "src-tauri/lu-core/proto/cognitum/memory/v1/evidence.proto",
}
MUTATED = {CORE / "src/lib.rs", CORE / "build.rs"}
MAX_LOG_BYTES = 2 * 1024 * 1024


class GateBlocked(RuntimeError):
    pass


def run_cmd(args: list[str], *, cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                              check=False, encoding="utf-8", errors="replace")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        raise GateBlocked(f"{args[0]} execution unavailable: {type(exc).__name__}") from exc


def git(root: Path, *args: str) -> str:
    result = run_cmd(["git", "-C", str(root), *args], cwd=root)
    if result.returncode:
        raise GateBlocked(f"git verification failed for {args[0]}")
    return result.stdout.rstrip("\n")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verified_source_state(root: Path) -> dict:
    """Reject active Lu changes and any overlay drift from this checkpoint."""
    if not root.is_dir() or not (root / ".git").exists():
        raise GateBlocked("a full disposable local Lu Git checkout is required")
    if git(root, "rev-parse", "HEAD") != PIN:
        raise GateBlocked("Lu HEAD differs from pinned source revision")
    allowed = set(OVERLAY_PATHS) | MUTATED
    # Git's tracked diff and untracked file list are checked independently.
    # --untracked-files=all ensures no extra file under a shared directory hides.
    changed = git(root, "diff", "--name-only", "HEAD", "--").splitlines()
    untracked = git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    paths = [Path(x) for x in changed + untracked]
    if len(paths) != len(set(paths)) or set(paths) != allowed:
        raise GateBlocked("Lu worktree changes must equal the five exact P8 overlay paths")
    for path, reference in OVERLAY_PATHS.items():
        installed = root / path
        if not reference.is_file() or not installed.is_file() or installed.is_symlink():
            raise GateBlocked("overlay source is missing or an unexpected symlink")
        if installed.read_bytes() != reference.read_bytes():
            raise GateBlocked(f"overlay source drift: {path.as_posix()}")
    original_lib = git(root, "show", f"{PIN}:{(CORE / 'src/lib.rs').as_posix()}") + "\n"
    original_build = git(root, "show", f"{PIN}:{(CORE / 'build.rs').as_posix()}") + "\n"
    if original_lib.count("pub mod ansf;\n") != 1:
        raise GateBlocked("missing audited Lu module anchor")
    expected_lib = original_lib.replace("pub mod ansf;\n", "pub mod ansf;\n"
        "pub mod ansf_memory_gate;\npub mod ansf_memory_proto;\n", 1)
    expected_build = original_build.replace(
        '.compile_protos(&["proto/lu/v1/core.proto"], &["proto"])',
        '.compile_protos(&["proto/lu/v1/core.proto", "proto/cognitum/memory/v1/evidence.proto"], &["proto"])', 1)
    if expected_build == original_build:
        raise GateBlocked("missing audited Lu Protobuf build anchor")
    if (root / CORE / "src/lib.rs").read_text(encoding="utf-8") != expected_lib:
        raise GateBlocked("unexpected Lu lib.rs changes")
    if (root / CORE / "build.rs").read_text(encoding="utf-8") != expected_build:
        raise GateBlocked("unexpected Lu build.rs changes")
    if git(root, "diff", "--name-only", "HEAD", "--", (CORE / "Cargo.toml").as_posix()):
        raise GateBlocked("Lu Cargo dependencies changed")
    return {"pinned_lu_commit": PIN, "five_overlay_files_verified": True,
            "overlay_sha256": {x.as_posix(): _sha256((root / x).read_bytes()) for x in sorted(allowed)}}


def native_gate(root: Path, *, mode: str = "all", report_path: Path | None = None) -> dict:
    """Runs only after strict worktree verification; 'preflight' never runs cargo."""
    root = root.resolve()
    report = {"milestone": "C06 P8", "native_gate": "BLOCKED", "rust_compiled": False,
              "host_authentication_tested": False, "lu_model_benchmarks_tested": False,
              "pinned_lu_commit": PIN, "checks": [], "error": None}
    try:
        report["source"] = verified_source_state(root)
        if mode == "preflight":
            report["native_gate"] = "PREFLIGHT_ONLY"
        else:
            for exe in ("cargo", "rustc"):
                if not shutil.which(exe):
                    raise GateBlocked(f"{exe} not on PATH; Rust test gate not executed")
            crate = root / CORE
            commands = (
                [["cargo", "test", "ansf_memory_gate", "--", "--nocapture"],
                 ["cargo", "test", "ansf_memory_proto", "--", "--nocapture"]]
                if mode == "scoped" else
                [["cargo", "test", "ansf_memory_gate", "--", "--nocapture"],
                 ["cargo", "test", "ansf_memory_proto", "--", "--nocapture"],
                 ["cargo", "test"]]
            )
            for command in commands:
                start = time.monotonic()
                proc = run_cmd(command, cwd=crate, timeout=600)
                logs = (proc.stdout + "\n" + proc.stderr)[-MAX_LOG_BYTES:]
                item = {"command": command, "returncode": proc.returncode,
                        "duration_sec": round(time.monotonic() - start, 3),
                        "log_sha256": _sha256(logs.encode()), "log_tail": logs[-2500:]}
                result_counts = [int(n) for n in re.findall(
                    r"test result:\s+ok\.\s+(\d+) passed;", logs)]
                item["tests_passed_reported"] = sum(result_counts)
                report["checks"].append(item)
                if proc.returncode != 0:
                    raise GateBlocked("native cargo test failed; see recorded command output")
                if item["tests_passed_reported"] == 0:
                    raise GateBlocked("cargo reported zero matching tests; refusing false success")
            report["rust_compiled"] = True
            report["native_gate"] = "PASS"
    except GateBlocked as exc:
        report["error"] = str(exc)
    if report_path is not None:
        report_path = report_path.resolve()
        if report_path.is_relative_to(root):
            raise GateBlocked("report destination must be outside Lu checkout")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lu-root", required=True, type=Path)
    parser.add_argument("--mode", choices=("preflight", "scoped", "all"), default="all")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    result = native_gate(args.lu_root, mode=args.mode, report_path=args.report)
    print(json.dumps({k: v for k, v in result.items() if k != "source"}, indent=2))
    return 0 if result["native_gate"] in ("PASS", "PREFLIGHT_ONLY") else 2


if __name__ == "__main__":
    sys.exit(main())
