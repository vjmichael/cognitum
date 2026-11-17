"""Test-only discovery of installed CPU Z3; never a runtime registry or grant."""
import importlib.util
import os
from pathlib import Path

def z3_library():
    spec=importlib.util.find_spec("z3")
    root=Path(spec.origin).parent if spec and spec.origin else None
    names=("libz3.dll","z3.dll","libz3.so","libz3.so.4","libz3.dylib")
    candidates=([root/"lib"/name for name in names] if root else [])
    candidates += [Path("/lib/x86_64-linux-gnu/libz3.so.4"),
                   Path("/usr/lib/x86_64-linux-gnu/libz3.so.4")]
    for path in candidates:
        if path.is_file():
            return path.resolve(strict=True)
    if os.environ.get("COG06B_REQUIRE_NATIVE")=="1":
        raise RuntimeError("required CPU Z3 library not found in installed package or system")
    return None
