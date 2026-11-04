"""Install and verify every declared Cognitum optional dependency group together.

Use on an isolated CI runner/venv; this deliberately tests the dependency
coexistence problem rather than demonstrating component correctness.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path


def extra_names(pyproject: Path, *, include_gpl: bool) -> list[str]:
    with pyproject.open("rb") as stream:
        data = tomllib.load(stream)
    extras = data["project"]["optional-dependencies"]
    if not isinstance(extras, dict) or not extras:
        raise ValueError("No optional dependency groups defined")
    names = sorted(extras)
    if not include_gpl:
        names = [name for name in names if name != "causal-timeseries-gpl"]
    if not names:
        raise ValueError("No dependency groups to test")
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--include-gpl", action="store_true",
                        help="Include GPL research dependencies for isolated compatibility testing only")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    names = extra_names(args.pyproject, include_gpl=args.include_gpl)
    target = f".[{','.join(names)}]"
    print(f"Python: {sys.version}", flush=True)
    print(f"Simultaneous optional extras ({len(names)}): {', '.join(names)}", flush=True)
    print(f"Install target: {target}", flush=True)
    if args.dry_run:
        return 0
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", target], check=True)
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    print("ALL DECLARED EXTRAS RESOLVED AND PIP CHECK PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
