"""Evaluate real-data availability and stage byte-preserved MOT17 and MPNTrack inputs.

Example:
PYTHONPATH=. python tools/run_c15_p2h_gate.py --data-zip /data/TrackEval/data.zip \\
    --labels-zip /data/MOT17Labels.zip --stage /tmp/mot17_stage --out /tmp/gate.json
"""
import argparse
import json
from pathlib import Path
from cognitum.spatial_mot17_realdata_gate import stage_mot17,evaluate_with_official_trackeval

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-zip',required=True,type=Path)
    p.add_argument('--labels-zip',required=True,type=Path)
    p.add_argument('--stage',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--sequence',action='append',help='repeat for selected MOT17-train sequences')
    p.add_argument('--trackeval-root',type=Path,help='optional externally obtained unmodified TrackEval checkout')
    p.add_argument('--source-zip',type=Path,help='uploaded TrackEval-master.zip, exact pinned tree verification')
    p.add_argument('--legacy-numpy-compat',action='store_true',help='opt-in legacy NumPy dtype aliases (does not modify TrackEval)')
    args=p.parse_args()
    result=stage_mot17(example_zip=args.data_zip,mot17_labels_zip=args.labels_zip,
                       output=args.stage,sequences=args.sequence)
    result['external_evaluation']=evaluate_with_official_trackeval(
        result,trackeval_root=args.trackeval_root,source_zip=args.source_zip,
        legacy_numpy_compat=args.legacy_numpy_compat)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'sequences':len(result['sequences']),
                      'external':result['external_evaluation']},sort_keys=True))

if __name__=='__main__':main()
