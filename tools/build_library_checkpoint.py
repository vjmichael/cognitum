"""Build/verify a deterministic, integrity-checked Cognitum Library source ZIP.

No network or Git required. The ZIP is a *source checkpoint*, not a Git commit.
Excludes secret-looking or non-source ephemeral paths. Verify every entry
before trusting a checkpoint from ChatGPT Library in a new session.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ALLOWED_TOP = {".gitignore", "README.md", "pyproject.toml", "SHA256SUMS.json"}
ALLOWED_DIR = {".github", "cognitum", "docs", "evals", "integrations", "proto", "research", "tests", "tools"}
DENIED_PARTS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
                ".ruff_cache", "node_modules", ".idea", ".vscode", "secrets", "private_keys"}
MANIFEST = "CHECKPOINT_INFO.json"


def approved(path: PurePosixPath):
    parts = path.parts
    if not parts or any(p in DENIED_PARTS or p.startswith(".env") for p in parts):
        return False
    if any(p.endswith((".pyc", ".pyo", ".pem", ".key", ".p12", ".db", ".sqlite", ".sqlite3", ".zip")) for p in parts):
        return False
    if len(parts) == 1:
        return parts[0] in ALLOWED_TOP
    return parts[0] in ALLOWED_DIR


def _safe_path(name):
    item = PurePosixPath(name)
    return bool(name and item.as_posix() == name and not name.startswith("/") and "\\" not in name and
                all(part not in ("", ".", "..") for part in item.parts) and
                not name.endswith("/"))


def pack(root: Path, archive: Path, *, base_snapshot: str, validation: dict,
         milestone="C06 P7 Lu host-fenced source updates and Protobuf bridge candidate (not compiled)",
         limitations=None, parent_checkpoint_sha256=None):
    root = root.resolve()
    archive = archive.resolve()
    sources = []
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.is_symlink():
            continue
        rel = f.relative_to(root).as_posix()
        if approved(PurePosixPath(rel)):
            sources.append((rel, f.read_bytes()))
    if not sources:
        raise ValueError("no approved source files")
    metadata = {
        "checkpoint_version": 2,
        "project": "Cognitum",
        "milestone": milestone,
        "baseline_git_sha": base_snapshot,
        "source_file_count": len(sources),
        "source_sha256": {path: hashlib.sha256(data).hexdigest() for path, data in sources},
        "validation": validation,
        "parent_checkpoint_sha256": parent_checkpoint_sha256,
        "limitations": limitations if limitations is not None else ["candidate Lu Rust ANSF gate and mutation-authority bridge staged but not cargo-compiled or installed",
                        "no production authenticated host admission; all ANSF writers not intercepted",
                        "no Lu physical deletion/purge protocol", "no model-facing CE",
                        "C07 SQLite derived event journal is a Python reference, not a Lu-authorized production writer; C07 physical purge is unimplemented",
                        "local Rust compiler unavailable; native Rust tests not executed",
                        "no real Lu+model benchmark"],
    }
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path, data in sources + [(MANIFEST, json.dumps(metadata, sort_keys=True, indent=2).encode() + b"\n")]:
            zi = zipfile.ZipInfo(path, (1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o100644 << 16
            z.writestr(zi, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    verify(archive)
    return metadata


def verify(archive: Path):
    with zipfile.ZipFile(archive) as z:
        allnames = z.namelist()
        if len(allnames) != len(set(allnames)) or not all(_safe_path(x) for x in allnames):
            raise ValueError("unsafe or duplicate ZIP entries")
        if MANIFEST not in allnames:
            raise ValueError("missing checkpoint manifest")
        for item in z.infolist():
            mode = (item.external_attr >> 16) & 0o170000
            if mode not in (0, 0o100000):
                raise ValueError("unexpected ZIP executable/symlink entry")
        metadata = json.loads(z.read(MANIFEST))
        expected = metadata["source_sha256"]
        if set(allnames) != set(expected).union({MANIFEST}) or metadata["source_file_count"] != len(expected):
            raise ValueError("checkpoint file set mismatch")
        for path, digest in expected.items():
            if not approved(PurePosixPath(path)) or hashlib.sha256(z.read(path)).hexdigest() != digest:
                raise ValueError("checkpoint integrity failure: " + path)
        if z.testzip() is not None:
            raise ValueError("damaged ZIP member")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pack")
    p.add_argument("source_root", type=Path)
    p.add_argument("archive", type=Path)
    p.add_argument("--base", required=True)
    p.add_argument("--unit-tests", type=int, required=True)
    p.add_argument("--replay", type=int, required=True)
    p.add_argument("--smoke", type=int, required=True)
    v = sub.add_parser("verify")
    v.add_argument("archive", type=Path)
    args = parser.parse_args()
    if args.command == "pack":
        metadata = pack(args.source_root, args.archive, base_snapshot=args.base,
                        validation={"unit_tests": args.unit_tests,
                                    "synthetic_replay": args.replay, "C03_smoke": args.smoke,
                                    "python_compileall": True,
                                    "independent_protoc_compilation": "pending"})
    else:
        metadata = verify(args.archive)
    print(json.dumps({"source_file_count": metadata["source_file_count"],
                      "milestone": metadata["milestone"], "validation": metadata["validation"]}, indent=2))


if __name__ == "__main__":
    main()
