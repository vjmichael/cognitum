"""C06/P9: opt-in, local-only Lu Rust test workspace orchestration.

Creates a disposable *sparse* clone from an existing local Lu Git checkout at
an exact pinned commit, applies the P7 overlay only to that clone, calls P8's
fail-closed native gate, and writes an evidence report outside either Git tree.
Neither local source checkout nor GitHub are modified. This tool cannot
bootstrap Rust or claim that any Rust tests ran if Cargo/rustc are unavailable.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

PARENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARENT))
import apply_overlay as installer  # noqa: E402
from p8 import native_gate as ng  # noqa: E402

PIN = ng.PIN


class WorkspaceBlocked(RuntimeError):
    pass


def _git(path: Path, *args: str, timeout: int = 120) -> str:
    try:
        result = subprocess.run(["git", "-C", str(path), *args],
                                capture_output=True, text=True, timeout=timeout,
                                encoding="utf-8", errors="replace", check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceBlocked(f"Git command unavailable: {args[0]}") from exc
    if result.returncode:
        # Never echo command output; Git errors can include credentialed URLs.
        raise WorkspaceBlocked(f"Local Git preflight failed: {args[0]}")
    return result.stdout.strip()


def _inside(candidate: Path, ancestor: Path) -> bool:
    return candidate == ancestor or ancestor in candidate.parents


def test_local_checkout(source: Path, output: Path, *, mode: str = "all",
                        allow_cargo_network: bool = False) -> dict[str, Any]:
    """Test an exact local Lu commit; leave original checkout byte-for-byte alone."""
    source = source.resolve(strict=True)
    output = output.resolve()
    if mode not in ("preflight", "scoped", "all"):
        raise WorkspaceBlocked("unknown test gate mode")
    if not (source / ".git").exists():
        raise WorkspaceBlocked("local Lu source must be a full Git checkout")
    if _inside(output, source):
        raise WorkspaceBlocked("report location must not be inside the Lu source checkout")
    if _inside(output, PARENT):
        raise WorkspaceBlocked("report location must not be inside the Cognitum overlay sources")
    if Path(_git(source, "rev-parse", "--show-toplevel")).resolve() != source:
        raise WorkspaceBlocked("source must be the Git checkout root")
    _git(source, "cat-file", "-e", PIN + "^{commit}")
    initial_head = _git(source, "rev-parse", "HEAD")
    initial_status = _git(source, "status", "--porcelain=v1", "--untracked-files=all")
    report: dict[str, Any] = {
        "milestone": "C06 P9", "test_mode": mode, "pinned_lu_commit": PIN,
        "source_checkout_untouched": True, "github_untouched": True,
        "native_gate": "BLOCKED", "rust_compiled": False,
        "host_authentication_tested": False, "lu_model_benchmarks_tested": False,
        "dependency_policy": "cargo network permitted" if allow_cargo_network else "offline only",
        "error": None, "checks": [],
    }
    work: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="cognitum-c06-p9-") as temp:
            work = Path(temp) / "lu-disposable"
            cmd = ["git", "clone", "--quiet", "--no-checkout", "--shared", "--",
                   str(source), str(work)]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, timeout=180, check=False)
            if proc.returncode:
                raise WorkspaceBlocked("offline sparse clone from local Lu checkout failed")
            _git(work, "sparse-checkout", "init", "--cone")
            _git(work, "sparse-checkout", "set", "src-tauri/lu-core")
            _git(work, "checkout", "--detach", PIN)
            if _git(work, "rev-parse", "HEAD") != PIN:
                raise WorkspaceBlocked("isolated clone source revision mismatch")
            # Installer validates ALL prerequisites before writing to the clone.
            changes = installer.prepare(work, PARENT)
            if len(changes) != 5:
                raise WorkspaceBlocked("unexpected overlay write set")
            for target, blob in changes.items():
                if not _inside(target.resolve(), work.resolve()):
                    raise WorkspaceBlocked("overlay path escapes disposable clone")
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    target.write_bytes(blob)
                else:
                    with target.open("xb") as f:
                        f.write(blob)
            previous = os.environ.get("CARGO_NET_OFFLINE")
            try:
                if not allow_cargo_network:
                    os.environ["CARGO_NET_OFFLINE"] = "true"
                elif previous is not None:
                    del os.environ["CARGO_NET_OFFLINE"]
                result = ng.native_gate(work, mode=mode)
            finally:
                if previous is None:
                    os.environ.pop("CARGO_NET_OFFLINE", None)
                else:
                    os.environ["CARGO_NET_OFFLINE"] = previous
            report.update({k: v for k, v in result.items() if k != "milestone"})
            report["milestone"] = "C06 P9"
            lock = work / ng.CORE / "Cargo.lock"
            if lock.is_file():
                import hashlib
                report["resolved_cargo_lock_sha256"] = hashlib.sha256(lock.read_bytes()).hexdigest()
            report["disposable_checkout_removed"] = True
    except (WorkspaceBlocked, ValueError, OSError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError) as exc:
        report["error"] = f"{type(exc).__name__}: {str(exc)[:350]}"
        report["native_gate"] = "BLOCKED"
    # Recheck tracked/untracked state in the original checkout. Its original
    # local edits are allowed but must not change during this operation.
    try:
        unchanged = (_git(source, "rev-parse", "HEAD") == initial_head and
                     _git(source, "status", "--porcelain=v1", "--untracked-files=all") == initial_status)
    except WorkspaceBlocked:
        unchanged = False
    report["source_checkout_untouched"] = unchanged
    if not unchanged:
        report["native_gate"] = "BLOCKED"
        report["rust_compiled"] = False
        report["error"] = "Local Lu source checkout changed during verification; manual audit required"
    report["disposable_checkout_removed"] = not bool(work and work.exists())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lu-source", required=True, type=Path,
                        help="existing local Lu Git checkout containing the exact pinned commit")
    parser.add_argument("--report", required=True, type=Path,
                        help="output JSON outside both source trees")
    parser.add_argument("--mode", choices=("preflight", "scoped", "all"), default="all")
    parser.add_argument("--allow-cargo-network", action="store_true",
                        help="opt in to Cargo dependency downloads; Git source still stays local")
    args = parser.parse_args(argv)
    try:
        data = test_local_checkout(args.lu_source, args.report, mode=args.mode,
                                   allow_cargo_network=args.allow_cargo_network)
    except (WorkspaceBlocked, FileNotFoundError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({k: v for k, v in data.items()
                      if k in ("native_gate", "rust_compiled", "error", "pinned_lu_commit",
                               "disposable_checkout_removed", "dependency_policy")}, indent=2))
    return 0 if data["native_gate"] in ("PASS", "PREFLIGHT_ONLY") else 2


if __name__ == "__main__":
    sys.exit(main())
