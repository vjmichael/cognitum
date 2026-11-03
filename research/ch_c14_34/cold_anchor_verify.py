"""Fresh-process metadata-only check of all 15 CH34 anchored ledger heads.
This does NOT mathematically replay MPFR: use audit34.py for that.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
D=Path(__file__).resolve().parent;sys.path.insert(0,str(D))
from anchor34 import AnchorLedger

def run(results_path=None,storage_path=None):
    results_path=Path(results_path or D/'anchor_results.json')
    storage_path=Path(storage_path or D/'anchor_storage')
    cases=json.loads(results_path.read_text())['results']
    if len(cases)!=15 or len(set(x['case_id'] for x in cases))!=15:
        raise ValueError('Expected exactly the 15 frozen CH23 cases')
    for x in cases:
        actual=AnchorLedger(storage_path/x['case_id']).read(
            expected_tip_sha256=x['externally_retain_tip_sha256'])
        b=actual['body']
        if (b['case_id'],b['original_head_sha256'],b['checkpoint_sha256'],
            b['nodes'],b['mpfr_replayed_frames'],b['archive_epochs']) != (
            x['case_id'],x['original_head_sha256'],x['checkpoint_sha256'],127,6,2):
            raise ValueError('Stored anchor metadata mismatches original proof identity')
    print('CH34 independent process: 15/15 externally supplied proposed pins and full immutable ledger histories validated; MPFR not rerun')
if __name__=='__main__':run(*(sys.argv[1:3]))
