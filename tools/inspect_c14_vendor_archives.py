"""Offline, read-only third-party causal-source archive admission report.

Provenance inspection is NOT source authentication, installation, execution,
Windows sandbox attestation, or permission to release a model-callable worker.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

CANDIDATES = {
    "dowhy": {"version": "0.14", "module": "dowhy", "metadata": "pyproject.toml", "version_file": "dowhy/__init__.py", "dependencies": ("numpy", "scipy", "pandas", "networkx", "statsmodels", "sympy", "sklearn", "causallearn", "econml", "cvxpy")},
    "econml": {"version": "0.17.0", "module": "econml", "metadata": "pyproject.toml", "version_file": "econml/_version.py", "dependencies": ("numpy", "scipy", "sklearn", "sparse", "numba", "shap", "joblib")},
    "causal-learn": {"version": "0.1.4.8", "module": "causallearn", "metadata": "setup.py", "version_file": "setup.py", "dependencies": ("numpy", "scipy", "sklearn", "momentchi2", "statsmodels", "pandas", "networkx", "graphviz", "pydot", "joblib")},
}
MAX_MEMBERS = 20000
MAX_UNCOMPRESSED = 1024 * 1024 * 1024


def inspect_archive(path: Path, package: str) -> dict:
    if package not in CANDIDATES:
        raise ValueError("Unknown package")
    p = Path(path)
    result = {"package": package, "requested_version": CANDIDATES[package]["version"],
              "archive_filename": p.name, "archive_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
              "source_declared_version": None, "version_state": "NOT_VERIFIED", "safe": False}
    cfg = CANDIDATES[package]
    with zipfile.ZipFile(p) as z:
        items = z.infolist()
        if not items or len(items) > MAX_MEMBERS:
            raise ValueError("ARCHIVE_MEMBER_LIMIT")
        names = [i.filename for i in items]
        if len(names) != len(set(names)):
            raise ValueError("DUPLICATE_ARCHIVE_MEMBER")
        roots = set()
        total = 0
        nonregular = []
        for i in items:
            n = i.filename.rstrip("/")
            parts = PurePosixPath(n).parts
            if (not n or n.startswith("/") or "\\" in n or ":" in n or
                any(x in ("", ".", "..") for x in parts) or not parts):
                raise ValueError("UNSAFE_ARCHIVE_PATH")
            mode = (i.external_attr >> 16) & 0o170000
            if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                if mode == stat.S_IFLNK:
                    nonregular.append(i.filename)  # inspect only; NEVER extract as a link
                else:
                    raise ValueError("UNSAFE_ARCHIVE_FILE_TYPE")
            roots.add(parts[0]); total += i.file_size
            if total > MAX_UNCOMPRESSED:
                raise ValueError("UNCOMPRESSED_ARCHIVE_LIMIT")
        if len(roots) != 1:
            raise ValueError("MULTIPLE_ARCHIVE_ROOTS")
        root = next(iter(roots))
        def read(relative: str) -> str:
            try: return z.read(root + "/" + relative).decode("utf-8", "replace")
            except KeyError: raise ValueError("MISSING_PROJECT_FILE:" + relative) from None
        metadata = read(cfg["metadata"])
        source = read(cfg["version_file"])
        if package == "dowhy":
            # A GitHub branch ZIP with dynamic-vcs versioning does not establish v0.14.
            m = re.search(r'^__version__\s*=\s*[\'\"]([^\'\"]+)', source, re.M)
            declared = m.group(1) if m else None
            dynamic = bool(re.search(r'^dynamic\s*=\s*\[\s*[\'\"]version[\'\"]\s*\]', metadata, re.M))
            result["version_state"] = "DYNAMIC_VCS_TAG_NOT_PROVEN" if dynamic else "DECLARED_VERSION_ONLY"
        elif package == "econml":
            m = re.search(r'^__version__\s*=\s*[\'\"]([^\'\"]+)', source, re.M)
            declared = m.group(1) if m else None
            result["version_state"] = "DECLARED_VERSION_MATCH" if declared == cfg["version"] else "VERSION_MISMATCH_OR_MISSING"
        else:
            m = re.search(r'^VERSION\s*=\s*[\'\"]([^\'\"]+)', source, re.M)
            declared = m.group(1) if m else None
            result["version_state"] = "DECLARED_VERSION_MATCH" if declared == cfg["version"] else "VERSION_MISMATCH_OR_MISSING"
        result.update({"source_declared_version": declared, "safe": True,
                       "safe_to_extract_without_filter": not nonregular,
                       "excluded_link_entries": nonregular,
                       "project_root": root, "members": len(items), "uncompressed_bytes": total,
                       "exact_release_authenticated": False,
                       "note": "Source declaration is not an authenticated Git commit or signed wheel; dynamic-version branch archives are not release pin evidence."})
    return result


def dependency_inventory() -> dict:
    out = {}
    for name, cfg in CANDIDATES.items():
        deps = {}
        for module in cfg["dependencies"]:
            try:
                deps[module] = importlib.util.find_spec(module) is not None
            except (ImportError, ModuleNotFoundError, ValueError):
                deps[module] = False
        out[name] = {"module": cfg["module"], "available_imports_in_current_interpreter": deps,
                     "unavailable_imports": sorted([k for k, v in deps.items() if not v])}
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__)
    for key in CANDIDATES:
        a.add_argument("--" + key, type=Path, required=True)
    a.add_argument("--output", type=Path, required=True)
    args = a.parse_args()
    paths = {"dowhy": args.dowhy, "econml": args.econml, "causal-learn": getattr(args, "causal_learn")}
    report = {"schema": "cognitum.c14.vendor-source-preflight.v1", "archives": [],
              "dependency_inventory": dependency_inventory(),
              "runtime_gate": "NOT_VERIFIED", "windows_lu_gate": "NOT_VERIFIED"}
    for name, path in paths.items():
        try: report["archives"].append(inspect_archive(path, name))
        except Exception as e:
            report["archives"].append({"package": name, "safe": False, "error": str(e)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(args.output)
    return 0 if all(item.get("safe") for item in report["archives"]) else 1

if __name__ == "__main__":
    raise SystemExit(main())
