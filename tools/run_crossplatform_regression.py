"""Repository-wide portable regression with explicit Linux-kernel test ownership.

All tests run on Linux. On Windows, the five kernel-specific modules are
listed as NOT RUN (never counted as passes), while every other test runs.
New unknown tests are included by default. The ownership manifest is
asserted against the test inventory to prevent silently stale exclusions.
"""
from pathlib import Path
import os
import sys
import unittest

LINUX_KERNEL_ONLY=frozenset({
    "test_host_recovery",
    "test_lu_linux_readiness",
    "test_p46r5_handoff_integration",
    "test_p46r8_recovery_cli_hardening",
    "test_recovery_service",
})

def main()->int:
    root=Path(__file__).resolve().parent.parent
    test_root=root/"tests"
    modules=sorted(p.stem for p in test_root.glob("test_*.py"))
    missing=LINUX_KERNEL_ONLY-set(modules)
    if missing:
        raise RuntimeError("Linux-kernel-only module manifest drift: "+repr(sorted(missing)))
    loader=unittest.TestLoader()
    if os.name=="nt":
        print("Windows: these Linux-kernel suites are NOT RUN:",flush=True)
        for module in sorted(LINUX_KERNEL_ONLY):
            print("  NOT_RUN_ON_WINDOWS "+module,flush=True)
        sys.path.insert(0,str(test_root))
        suite=unittest.TestSuite(loader.loadTestsFromName(name) for name in modules
                                 if name not in LINUX_KERNEL_ONLY)
    else:
        print("Linux: running every Python regression test (including kernel suites)",flush=True)
        suite=loader.discover(str(test_root),pattern="test_*.py")
    outcome=unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if outcome.wasSuccessful() else 1

if __name__=="__main__":
    sys.exit(main())
