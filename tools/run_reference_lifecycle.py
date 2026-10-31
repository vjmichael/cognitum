"""Execute the fixed P48 Linux reference lifecycle probes (NOT P46 or a sandbox)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cognitum.reference_lifecycle import run_reference_probe


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)
    result = run_reference_probe()
    # Write only the strict P47 receipt. The evaluation is separate, not signed.
    payload = (json.dumps(result['receipt'], sort_keys=True, indent=2) + '\n').encode('utf-8')
    with args.out.open('xb') as stream:
        stream.write(payload)
    print(json.dumps(result['evaluation'], sort_keys=True, indent=2))
    return 0 if result['evaluation']['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
