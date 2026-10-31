"""P47 strict, bounded lifecycle evidence validator (not a native test runner)."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# Permits direct execution from the repository checkout, with no installation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cognitum.lifecycle_evidence import InvalidEvidence, verify_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", help="JSON receipt from the independent native probe runner")
    parser.add_argument("--source-sha256", help="expected exact SHA-256 of tested source")
    args = parser.parse_args(argv)
    try:
        result = verify_file(args.receipt, source_sha256=args.source_sha256)
    except (InvalidEvidence, OSError) as exc:
        result = {"status": "INVALID", "failures": [str(exc)],
                  "qualification": "structural-only; NOT OS isolation certification"}
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
