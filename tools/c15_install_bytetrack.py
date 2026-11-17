"""Explicit host/CI installation: verify exact published pure-Python wheel.

The CPU tracker package is separate from Cognitum's default install; use an
isolated environment to avoid mixing OpenCV GUI and headless distributions.
This script is build/test infrastructure, never a model-callable tool.
"""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from importlib.metadata import distribution, version, PackageNotFoundError
import subprocess, sys, json
from cognitum.spatial_bytetrack import VERSION,WHEEL_SHA256,UPSTREAM,_engine

def main():
    with TemporaryDirectory(prefix="c15-wheel-") as temp:
        subprocess.run([sys.executable,"-m","pip","download","--no-deps","--only-binary=:all:",
                        "--dest",temp,"trackers=="+VERSION],check=True,timeout=180)
        wheel=Path(temp)/("trackers-"+VERSION+"-py3-none-any.whl")
        if not wheel.is_file() or sha256(wheel.read_bytes()).hexdigest()!=WHEEL_SHA256:
            raise RuntimeError("unreviewed ByteTrack distribution")
        subprocess.run([sys.executable,"-m","pip","install",str(wheel)],check=True,timeout=600)
    subprocess.run([sys.executable,"-m","pip","check"],check=True,timeout=60)
    _,_,_,identity=_engine()
    packages={}
    for name in ("trackers","numpy","scipy","supervision","opencv-python","requests","rich","pydeprecate"):
        d=distribution(name)
        packages[name]={"version":d.version,"license":d.metadata.get("License-Expression") or
                        d.metadata.get("License"),"requires":d.requires}
    print(json.dumps({"wheel_sha256":WHEEL_SHA256,"upstream":UPSTREAM,"backend_sha256":identity,
                      "direct_dependency_metadata":packages},indent=2))
if __name__=="__main__":main()
