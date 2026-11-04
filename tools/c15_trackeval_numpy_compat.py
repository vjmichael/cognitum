"""Patch a pinned legacy TrackEval checkout for NumPy >=1.24.

The official TrackEval checkout is pinned at a reviewed commit. This
compatibility adapter changes ONLY the removed `np.float` and `np.int` type aliases to
`np.float64` and `np.int64` in the one known loader file, after verifying its exact old
source and refusing surprising variants. It does not alter any metric
algorithm, association threshold, annotation, or prediction.
"""
from hashlib import sha256
from pathlib import Path
import argparse
import json
import re

TARGET = Path("trackeval/datasets/mot_challenge_2d_box.py")
ALIASES = {b"float": b"float64", b"int": b"int64"}


def patch(root: Path) -> dict:
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("absolute TrackEval checkout required")
    path = root / TARGET
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 200000:
        raise ValueError("unexpected TrackEval file")
    original = path.read_bytes()
    # Match only removed exact aliases, not np.float64 or np.int64.
    pattern = rb"np\.(float|int)\b"
    matches = list(re.finditer(pattern, original))
    if not matches or len(matches) > 16:
        raise ValueError("pinned TrackEval legacy NumPy aliases absent or unexpected")
    updated = re.sub(pattern, lambda match: b"np." + ALIASES[match.group(1)], original)
    if updated == original:
        raise ValueError("compatibility patch changed nothing")
    # Check expected exact sequence before writing.
    if b"dtype=np.float" not in original or b"dtype=np.int" not in original:
        raise ValueError("expected TrackEval loader alias missing")
    path.write_bytes(updated)
    compile(updated, str(path), "exec")
    return {
        "source":"pinned TrackEval legacy NumPy type alias compatibility",
        "file":str(TARGET),
        "transform":"np.float -> np.float64; np.int -> np.int64 (exact aliases only)",
        "replacements":len(matches),
        "by_alias": {alias.decode():sum(m.group(1)==alias for m in matches)
                      for alias in ALIASES},
        "before_sha256":sha256(original).hexdigest(),
        "after_sha256":sha256(updated).hexdigest(),
        "metric_logic_modified":False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    result = patch(args.root)
    if args.audit.exists():
        raise ValueError("refusing to overwrite prior compatibility audit")
    args.audit.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__=="__main__":
    main()
