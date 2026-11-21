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
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile

MAX_FILES = 12000
MAX_FILE_BYTES = 128 * 1024 * 1024
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
        "benchmarks", "docs", "examples", "include", "lib2to3",
        "turtledemo", "tkinter", "idlelib", "ensurepip", "pip",
    ) or name.endswith(".pyc") or name.endswith(".pyo")}


def copytree(src, dst):
    need(src.is_dir() and not src.is_symlink() and not dst.exists(),
         "externally pinned source must exist exactly once")
    shutil.copytree(src,dst,symlinks=False,ignore=excluded)


def prepare(destination:Path, repo:Path):
    need(sys.platform=="win32","genuine native Windows Python runtime required")
    need(destination.is_absolute() and not destination.exists() and
         destination.parent.is_dir() and not destination.parent.is_symlink(),
         "fresh externally staged absolute package root required")
    repo=repo.resolve(strict=True)
    need((repo/"cognitum/mel/ssm_r5_fixed_child.py").is_file(),
         "reviewed fixed numerical entrypoint required")
    source_python=Path(sys.executable).resolve(strict=True)
    prefix=Path(sys.prefix).resolve(strict=True)
    need(source_python.parent==prefix and prefix.name.lower() in ("x64","amd64"),
         "unexpected exact GitHub Windows toolchain executable layout")
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
    for p in sorted(destination.rglob("*"),key=lambda x:x.as_posix().lower()):
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
    manifest.write_bytes(raw)
    report={
      "schema":"cognitum.ssm.r3r1.test_installer_style_frozen_runtime.v1",
      "python_sha256":hashfile(exe),
      "fixed_script_sha256":hashfile(script),
      "runtime_manifest_sha256":hashlib.sha256(raw).hexdigest(),
      "runtime_file_count":len(entries),
      "runtime_total_bytes":total,
      "selected_numpy_scipy":True,
      "closed_site_packages":True,
      "exact_package_owner_ACL_approved":False,
      "signed_installer_publisher_approved":False,
      "actual_Core_grant":False,
      "external_output_release_authorized":False,
    }
    (destination/"r3-r1-runtime-provenance.json").write_text(
         json.dumps(report,sort_keys=True,separators=(",",":"))+"\n",encoding="ascii")
    return report


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
             "actual frozen Python/NumPy/SciPy numerical smoke failed")
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
    parser.add_argument("mode",choices=["prepare","smoke"])
    parser.add_argument("--root",required=True)
    parser.add_argument("--repo")
    parser.add_argument("--request")
    args=parser.parse_args()
    if args.mode=="prepare":
        result=prepare(Path(args.root),Path(args.repo or Path(__file__).resolve().parents[1]))
    else:
        need(bool(args.request),"fixed smoke input required")
        result=smoke(Path(args.root),Path(args.request))
    print(json.dumps(result,sort_keys=True))
