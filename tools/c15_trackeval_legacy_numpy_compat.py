"""Opt-in compatibility launcher for pinned legacy TrackEval under NumPy >= 2.

Only reinstates deprecated NumPy dtype aliases consumed by old TrackEval code.
TrackEval's own Python source is never modified. This launcher is not an
independent evaluator or a replacement for TrackEval's metric implementation.
"""
from __future__ import annotations
import runpy
import sys
from pathlib import Path
import numpy as np

def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('Usage: c15_trackeval_legacy_numpy_compat.py SCRIPT [args...]')
    script = Path(sys.argv[1]).resolve()
    if script.name != 'run_mot_challenge.py' or not script.is_file():
        raise SystemExit('Expected an existing TrackEval run_mot_challenge.py script')
    for name, alias in [('float', float), ('int', int), ('bool', bool)]:
        if name not in vars(np):
            setattr(np, name, alias)
    sys.argv = [str(script)] + sys.argv[2:]
    runpy.run_path(str(script), run_name='__main__')

if __name__ == '__main__':
    main()
