"""Compare successive Cognitum ZIP checkpoints before any GitHub source import.

This is a *local* diff/inventory, not a GitHub-repository comparison and not
an acceptance test for real-world observations or Windows execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

SOURCE_ROOTS = ("cognitum/", "proto/", "tests/", "tools/", "docs/", "evals/", "integrations/", "standalone_windows_host/", "standalone_vm_recovery/")
SOURCE_FILES = frozenset(("pyproject.toml", "Run-Cognitum-T4-P13-Windows.cmd", "Run-Cognitum-VM-Recovery.cmd"))
EXCLUDED_SEGMENTS = frozenset(("__pycache__", ".pytest_cache", ".git", ".venv", "node_modules"))
MAX_ENTRY_BYTES = 10_000_000
MAX_TOTAL_BYTES = 120_000_000


class UnsafeCheckpoint(ValueError):
    pass


def classification(path: str) -> str:
    """Source candidate, generated/code-adjacent or external research evidence."""
    parts = path.split("/")
    if any(part in EXCLUDED_SEGMENTS for part in parts) or path.endswith((".pyc", ".pyo")):
        return "excluded_generated"
    if path == ".github/workflows/python-tests.yml" or path in SOURCE_FILES:
        return "source_candidate"
    if path.startswith(SOURCE_ROOTS):
        if path.startswith(("docs/", "evals/")) and path.endswith((".json", ".log", ".csv")):
            return "review_research_data"
        return "source_candidate"
    return "review_checkpoint_evidence"


def inventory(path: Path) -> dict[str, dict]:
    result: dict[str, dict] = {}
    total = 0
    with zipfile.ZipFile(path, "r") as archive:
        for item in archive.infolist():
            name = item.filename
            # ZipInfo normalizes backslashes on Windows; orig_filename retains
            # the untrusted spelling before platform-specific normalization.
            if item.orig_filename != name:
                raise UnsafeCheckpoint(f"NORMALIZED_OR_UNSAFE_PATH:{item.orig_filename}")
            posix = PurePosixPath(name)
            if (not name or name.startswith("/") or "\\" in name or
                    ".." in posix.parts or ":" in posix.parts[0] or
                    str(posix) != name or name in result):
                raise UnsafeCheckpoint(f"UNSAFE_OR_DUPLICATE_PATH:{name}")
            mode = (item.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise UnsafeCheckpoint(f"SYMLINK_ENTRY:{name}")
            if item.is_dir():
                continue
            if item.file_size > MAX_ENTRY_BYTES:
                raise UnsafeCheckpoint(f"OVERSIZED_ENTRY:{name}")
            total += item.file_size
            if total > MAX_TOTAL_BYTES:
                raise UnsafeCheckpoint("OVERSIZED_ARCHIVE")
            data = archive.read(item)
            result[name] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "category": classification(name),
            }
    return result


def diff(before: Path, after: Path) -> dict:
    prev, nxt = inventory(before), inventory(after)
    added = sorted(set(nxt) - set(prev))
    deleted = sorted(set(prev) - set(nxt))
    changed = sorted(n for n in set(prev) & set(nxt) if prev[n]["sha256"] != nxt[n]["sha256"])
    unchanged = len(set(prev) & set(nxt)) - len(changed)
    changes = []
    for status, names in (("added", added), ("changed", changed), ("deleted", deleted)):
        for name in names:
            entry = nxt.get(name) or prev[name]
            changes.append({"path": name, "status": status, "category": entry["category"],
                            "old_sha256": prev.get(name, {}).get("sha256"),
                            "new_sha256": nxt.get(name, {}).get("sha256")})
    changes.sort(key=lambda x: (x["path"], x["status"]))
    return {"schema": 1, "gate": "COGNITUM-CHECKPOINT-SOURCE-RECONCILIATION",
            "github_repository_compared": False,
            "github_upload_approved": False,
            "research_only": True, "source_archive_before": before.name,
            "source_archive_after": after.name,
            "before_entries": len(prev), "after_entries": len(nxt),
            "unchanged": unchanged,
            "added": len(added), "changed": len(changed), "deleted": len(deleted),
            "changes": changes}


def main() -> int:
    parser = argparse.ArgumentParser(description="Review two Cognitum source checkpoint ZIPs")
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--out", type=Path, help="Write a new report file; existing files are never overwritten")
    args = parser.parse_args()
    try:
        report = diff(args.before, args.after)
    except (OSError, zipfile.BadZipFile, UnsafeCheckpoint, RuntimeError) as exc:
        parser.error(str(exc))
    data = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(data)
    if args.out is not None:
        # Exclusive create avoids accidental source/checkpoint replacement.
        with args.out.open("x", encoding="utf-8") as file:
            file.write(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
