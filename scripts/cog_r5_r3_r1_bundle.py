"""R3-R1 externally staged, version-fixed disposable Windows SSM runtime.

CI-only installer-style package custody; NOT a signed installed production
publisher. Copies a narrow CPython stdlib and exact pinned NumPy/SciPy,
Protobuf and cryptography dependencies plus the original reviewed Cognitum
code into one precreated directory. No network/model/runtime downloads, no
dynamic module requests, no secrets, no Core grant or output release.

An ASCII sorted all-file SHA256 manifest permits the SCM to verify EVERY
frozen import and DLL against a build-pinned manifest digest before the
restricted child is launched. The manifest is never an authority token and
its owner/ACL/package signer still require independent installed acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile

MAX_FILES = 12000
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_BYTES = 1400 * 1024 * 1024
REQUIRED_DEPS = ("numpy", "scipy", "google", "cryptography")
OPTIONAL_DEPS = ("numpy.libs", "scipy.libs", "cffi", "pycparser")


class BundleRefused(ValueError):
    pass


def need(ok, why):
    if not ok:
        raise BundleRefused("R3 frozen SSM runtime refused: " + why)


def hashfile(p: Path):
    need(p.is_file() and not p.is_symlink() and p.stat().st_size <= MAX_FILE_BYTES,
         "not an accepted bounded regular image/dependency")
    h=hashlib.sha256()
    with p.open("rb") as inp:
        for block in iter(lambda:inp.read(1<<20),b""):
            h.update(block)
    return h.hexdigest()


def excluded(directory, names):
    return {name for name in names if name in (
        "__pycache__", "tests", "test", "testing", ".git", ".github",
        "benchmarks", "docs", "examples", "include", "lib2to3", "site-packages",
        "turtledemo", "tkinter", "idlelib", "ensurepip", "pip",
    ) or name.endswith(".pyc") or name.endswith(".pyo")}


def copytree(src, dst):
    need(src.is_dir() and not src.is_symlink() and not dst.exists(),
         "externally pinned source must exist exactly once")
    shutil.copytree(src,dst,symlinks=False,ignore=excluded)


def prepare(destination:Path, repo:Path, *,
            production_source_sha=None,
            approved_manifest_sha256=None,
            approved_python_sha256=None):
    production = production_source_sha is not None
    if production:
        # This is an independently pinned *fresh build from original imports*.
        # It is NOT a promotion/rename of the CI fixture's provenance.
        need(os.environ.get("GITHUB_ACTIONS") != "true" and
             os.environ.get("CI") != "true",
             "hosted CI may not prepare production runtime")
        for value, length in ((production_source_sha, 40),
                              (approved_manifest_sha256, 64),
                              (approved_python_sha256, 64)):
            need(isinstance(value, str) and
                 re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) and
                 set(value) != {"0"},
                 "independent original source, manifest and Python image pins required")
        need(sys.maxsize > 2**32, "original native Windows x64 Python required")
    need(sys.platform=="win32","genuine native Windows Python runtime required")
    need(destination.is_absolute() and not destination.exists() and
         destination.parent.is_dir() and not destination.parent.is_symlink(),
         "fresh externally staged absolute package root required")
    repo=repo.resolve(strict=True)
    if production:
        try:
            rev=subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                               capture_output=True, text=True, timeout=10, check=True)
            dirty=subprocess.run(["git", "-C", str(repo), "status",
                                  "--porcelain", "--untracked-files=no"],
                                 capture_output=True, text=True, timeout=10, check=True)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            raise BundleRefused("R3 frozen SSM runtime refused: exact original Git source unavailable")
        need(rev.stdout.strip() == production_source_sha and
             not dirty.stdout.strip(),
             "production runtime exact Git source differs or has tracked edits")
    need((repo/"cognitum/mel/ssm_r5_fixed_child.py").is_file(),
         "reviewed fixed numerical entrypoint required")
    source_python=Path(sys.executable).resolve(strict=True)
    prefix=Path(sys.prefix).resolve(strict=True)
    need(source_python.parent==prefix and
         (production or prefix.name.lower() in ("x64","amd64")),
         "unexpected original native Windows Python executable layout")
    if production:
        need(hashfile(source_python) == approved_python_sha256,
             "original production Python image differs from external SHA256 pin")
    site=prefix/"Lib/site-packages"
    need(site.is_dir() and (site/"numpy").is_dir() and (site/"scipy").is_dir(),
         "NumPy and SciPy not pinned in the original Python runtime")
    destination.mkdir(mode=0o700)
    for name in ("python.exe","python3.dll",f"python{sys.version_info.major}{sys.version_info.minor}.dll",
                 "vcruntime140.dll","vcruntime140_1.dll"):
        source=prefix/name
        if name in ("python.exe",f"python{sys.version_info.major}{sys.version_info.minor}.dll"):
            need(source.is_file(),"required fixed CPython runtime image absent")
        if source.is_file():
            shutil.copy2(source,destination/name)
    copytree(prefix/"DLLs",destination/"DLLs")
    copytree(prefix/"Lib",destination/"Lib")
    # Excluding site-packages from the parent copy is mandatory; a dependency
    # enters the frozen package ONLY if explicitly reviewed below.
    copied_site=destination/"Lib/site-packages"
    need(not copied_site.exists(),"unreviewed entire site-packages was copied")
    copied_site.mkdir()
    for name in REQUIRED_DEPS+OPTIONAL_DEPS:
        src=site/name
        if name in REQUIRED_DEPS:
            need(src.is_dir(),"required pinned original package missing: "+name)
        if src.is_dir():
            copytree(src,copied_site/name)
        if name=="numpy":
            # numpy.testing is a public runtime-importable subpackage of
            # NumPy (and an indirect import on its normal import graph),
            # not an arbitrary research test suite. Restore this exact
            # upstream package, but still exclude its nested tests.
            required_testing=src/"testing"
            need((required_testing/"__init__.py").is_file(),
                 "required pinned numpy.testing import package missing")
            copytree(required_testing,copied_site/name/"testing")
            # NumPy 2.2's public numpy.testing imports pd_NA from this
            # single _core/tests support module during normal SciPy import.
            # Import exactly the pinned support file, never the test suite.
            natype=src/"_core"/"tests"/"_natype.py"
            need(natype.is_file() and not natype.is_symlink(),
                 "required NumPy _natype runtime support absent")
            private_support=copied_site/name/"_core"/"tests"
            private_support.mkdir()
            shutil.copy2(natype,private_support/"_natype.py")
    # Native extension/PE DLL modules that NumPy/SciPy/cryptography import.
    for pattern in ("_cffi_backend*.pyd","_cffi_backend*.dll"):
        for src in site.glob(pattern):
            need(src.is_file() and not src.is_symlink(),"foreign extension module")
            shutil.copy2(src,copied_site/src.name)
    # The Cog MEL code is the exact reviewed input; no user, model, remote
    # package or source tree is dynamically imported at runtime.
    copytree(repo/"cognitum",destination/"cognitum")
    pythonpth=destination/f"python{sys.version_info.major}{sys.version_info.minor}._pth"
    pythonpth.write_text(".\nLib\nDLLs\nLib\\site-packages\nimport site\n",
                         encoding="ascii",newline="\n")
    exe=destination/"python.exe"
    script=destination/"cognitum/mel/ssm_r5_fixed_child.py"
    need(exe.is_file() and script.is_file(),"fixed copied image/script incomplete")
    # Canonical manifest includes all files except itself and provenance.
    entries=[]
    total=0
    for p in sorted(destination.rglob("*"),key=lambda x:x.as_posix()):
        if not p.is_file():
            continue
        need(not p.is_symlink() and not any(parent.is_symlink() for parent in p.parents
                if parent==destination or destination in parent.parents),
             "reparse/symlinked dependency cannot enter pinned package")
        rel=p.relative_to(destination).as_posix()
        need("\t" not in rel and "\n" not in rel and "\r" not in rel and
             "\\" not in rel and ".." not in rel.split("/") and
             all(32<=ord(ch)<127 for ch in rel),
             "noncanonical or traversal dependency path")
        size=p.stat().st_size
        need(size<=MAX_FILE_BYTES and size>=0,"dependency size outside package budget")
        total+=size
        entries.append((rel,hashfile(p),size))
        need(total<=MAX_BUNDLE_BYTES and len(entries)<=MAX_FILES,
             "bounded frozen runtime package budget exceeded")
    manifest=destination/"r3-r1-runtime.manifest"
    raw="".join(f"{digest}\t{rel}\n" for rel,digest,_ in entries).encode("ascii")
    need(len(raw)<MAX_FILES*240,"frozen import manifest too large")
    manifest_digest=hashlib.sha256(raw).hexdigest()
    if production:
        # The external manifest pin MUST be known BEFORE this invocation.
        # There is deliberately no auto-approval, CI artifact promotion, or
        # fallback to a locally generated digest on disagreement.
        need(manifest_digest == approved_manifest_sha256,
             "fresh production import closure differs from external manifest approval")
    manifest.write_bytes(raw)
    report={
      "schema":("cognitum.ssm.r3r1.production_installer_runtime.v1"
                if production else
                "cognitum.ssm.r3r1.test_installer_style_frozen_runtime.v1"),
      "python_sha256":hashfile(exe),
      "fixed_script_sha256":hashfile(script),
      "runtime_manifest_sha256":manifest_digest,
      "runtime_file_count":len(entries),
      "runtime_total_bytes":total,
      "selected_numpy_scipy":True,
      "closed_site_packages":True,
      "original_production_source_sha":(production_source_sha if production else None),
      "external_python_image_sha256":(approved_python_sha256 if production else None),
      "production_release_signer_approved":False,
      "independent_release_authority_approved":False,
      "exact_package_owner_ACL_approved":False,
      "signed_installer_publisher_approved":False,
      "actual_Core_grant":False,
      "external_output_release_authorized":False,
    }
    (destination/"r3-r1-runtime-provenance.json").write_text(
         json.dumps(report,sort_keys=True,separators=(",",":"))+"\n",encoding="ascii")
    return report


def _smoke_refusal(stderr:bytes, returncode:int)->str:
    """Bounded, path/secret-free diagnostics for CI-only numerical process."""
    status=f"exit={returncode & 0xffffffff:08x}"
    text=stderr[:32768].decode("utf-8",errors="replace")
    patterns=(
      (r"ModuleNotFoundError: No module named ['\\\"]([A-Za-z_][A-Za-z0-9_.]{0,63})['\\\"]", "missing_module"),
      (r"DLL load failed while importing ([A-Za-z_][A-Za-z0-9_]{0,63})", "dll_import"),
      (r"ImportError: .*?([A-Za-z_][A-Za-z0-9_]{0,63})", "import_error"),
    )
    for pattern,kind in patterns:
        match=re.search(pattern,text)
        if match:
            return f"{kind}:{match.group(1)};{status}"
    if "Fatal Python error:" in text:
        return "interpreter_initialization;"+status
    if "Traceback (most recent call last):" in text:
        return "python_exception;"+status
    if returncode==3:
        return "fixed_ssm_child_rejected_input;"+status
    return "native_process_or_unknown;"+status


def smoke(directory:Path,request:Path):
    need(sys.platform=="win32","native Windows frozen SSM required")
    directory=directory.resolve(strict=True)
    python=directory/"python.exe"
    child=directory/"cognitum/mel/ssm_r5_fixed_child.py"
    need(python.is_file() and child.is_file() and request.is_file(),
         "pinned frozen SSM executable/worker/request absent")
    with tempfile.TemporaryDirectory(prefix="r3r1-ssm-smoke-",dir=directory.parent) as tmp:
        root=Path(tmp)
        data=root/"input.frame"
        out=root/"output.frame"
        shutil.copy2(request,data)
        result=subprocess.run([str(python),"-I","-B",str(child),str(data),str(out)],
            cwd=directory,timeout=40,env={
             "SystemRoot":os.environ["SystemRoot"],"TEMP":str(root),
             "TMP":str(root),"WINDIR":os.environ["SystemRoot"],
            },capture_output=True)
        need(result.returncode==0 and out.is_file(),
             "actual frozen Python/NumPy/SciPy numerical smoke failed ("+
             _smoke_refusal(result.stderr,result.returncode)+")")
        reply=json.loads(out.read_bytes())
        need(reply.get("status")=="ok" and type(reply.get("reply")) is dict,
             "frozen numerical code did not produce bounded candidate")
        return {
          "schema":"cognitum.ssm.r3r1.local_frozen_math_smoke.v1",
          "full_Python_NumPy_SciPy_request_executed":True,
          "appcontainer_token_qualified":False,
          "Core_grant":False,
          "output_release_authorized":False,
        }


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=["prepare","prepare-production","smoke"])
    parser.add_argument("--source-sha")
    parser.add_argument("--approved-manifest-sha256")
    parser.add_argument("--approved-python-sha256")
    parser.add_argument("--root",required=True)
    parser.add_argument("--repo")
    parser.add_argument("--request")
    args=parser.parse_args()
    if args.mode in ("prepare", "prepare-production"):
        if args.mode == "prepare-production":
            need(bool(args.source_sha and args.approved_manifest_sha256 and
                      args.approved_python_sha256),
                 "separately approved original Git, manifest and CPython pins required")
        result=prepare(
            Path(args.root),Path(args.repo or Path(__file__).resolve().parents[1]),
            production_source_sha=(args.source_sha if args.mode=="prepare-production" else None),
            approved_manifest_sha256=(args.approved_manifest_sha256 if args.mode=="prepare-production" else None),
            approved_python_sha256=(args.approved_python_sha256 if args.mode=="prepare-production" else None),
        )
    else:
        need(bool(args.request),"fixed smoke input required")
        result=smoke(Path(args.root),Path(args.request))
    print(json.dumps(result,sort_keys=True))
