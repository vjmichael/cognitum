"""Quote-free launcher for the Zog Zoo HDC package (toolkit quote-safety shim).

Usage (from any shell, no quotes needed):
    C:\\Python314\\python.exe C:\\Users\\UserMN4312\\Documents\\run_zz.py selftest
    C:\\Python314\\python.exe C:\\Users\\UserMN4312\\Documents\\run_zz.py smoke
    C:\\Python314\\python.exe C:\\Users\\UserMN4312\\Documents\\run_zz.py run
"""
import os
import sys

DEV = r"C:\Users\UserMN4312\Documents\Zog Zoo\Zog Zoo Dev"
os.chdir(DEV)
sys.path.insert(0, DEV)

mode = sys.argv[1] if len(sys.argv) > 1 else "selftest"

if mode == "selftest":
    from zogzoo_hdc import selftest
    ok = selftest.run_all()
    print("RESULT:", "OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)
elif mode == "smoke":
    from zogzoo_hdc.cli import main
    sys.exit(main(["smoke"]))
elif mode == "run":
    cfg_path = os.path.join(DEV, "configs", "default_run.json")
    from zogzoo_hdc.cli import main
    sys.exit(main(["run", "--config", cfg_path]))
else:
    print("unknown mode", mode)
    sys.exit(2)