"""Run genuine cross-platform unittest suite with explicit OS-only partition.

Linux cgroup2/P46 native-worker tests cannot be imported/executed on Windows
(fcntl, os.pipe2, kernel cgroups). They are *not* silently counted as passing:
print their exact modules, and execute them in the Linux matrix. All portable
tests, including C15 and real optional SciPy/OpenCV, run on both OSes.
"""
import os
import sys
import unittest

LINUX_ONLY_MODULES=frozenset({
    "test_host_recovery",
    "test_lu_linux_readiness",
    "test_p46r5_handoff_integration",
    "test_p46r8_recovery_cli_hardening",
    "test_recovery_service",
})


def main():
    loader=unittest.TestLoader()
    if os.name=="nt":
        print("WINDOWS: Linux-exclusive modules are NOT EXECUTED:",flush=True)
        for name in sorted(LINUX_ONLY_MODULES):
            print("  NOT_RUN_ON_WINDOWS:",name,flush=True)
        # Do not import Linux-only modules on Windows. unittest imports when
        # discovering so discover portable modules directly, by filename.
        from pathlib import Path
        tests=sorted(Path("tests").glob("test_*.py"))
        names={f.stem for f in tests}
        missing=LINUX_ONLY_MODULES-names
        if missing:
            raise RuntimeError("Linux-only test manifest drift: "+str(sorted(missing)))
        suites=[]
        for path in tests:
            if path.stem in LINUX_ONLY_MODULES:
                continue
            suites.append(loader.loadTestsFromName(path.stem))
        # Add tests directory to import path, like unittest discover does.
        sys.path.insert(0,str(Path("tests").resolve()))
        suites=[loader.loadTestsFromName(p.stem) for p in tests
                if p.stem not in LINUX_ONLY_MODULES]
        print("PORTABLE TEST MODULES:",len(suites),flush=True)
        suite=unittest.TestSuite(suites)
    else:
        print("LINUX: run ALL core/portable/kernel-specific test modules",flush=True)
        suite=loader.discover("tests",pattern="test_*.py")
    outcome=unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if outcome.wasSuccessful() else 1


if __name__=="__main__":
    sys.exit(main())
