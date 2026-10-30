"""Build strict C15 T1 P2F TrackEval MOTChallenge staging, optionally run genuine engine.

Requires separately supplied actual GT / tracker prediction files and optional
TrackEval checkout. No detector, video, feature model, or TrackEval is shipped.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from cognitum.proto import benchmark_observation_pb2 as pb
from cognitum.spatial_benchmark_observation import read_mot_benchmark, ObservationRejected
from cognitum.spatial_trackeval_bridge import stage_motchallenge, run_trackeval


def run(args):
    if Path(args.gt).resolve()==Path(args.pred).resolve():
        raise ObservationRejected('IDENTICAL_GT_AND_PRED_FILES')
    common=dict(seq=args.sequence,width=args.width,height=args.height,
        dataset_id=args.dataset_id,dataset_version=args.dataset_version)
    gt=read_mot_benchmark(args.gt,role=pb.GROUND_TRUTH,source_uri=args.gt_source,
        legacy_gt=args.legacy_gt,**common)
    pred=read_mot_benchmark(args.pred,role=pb.TRACKER_PREDICTION,
        source_uri=args.pred_source,**common)
    staging=stage_motchallenge(gt,pred,root=args.staging,sequence=args.sequence,
        tracker=args.tracker,benchmark=args.benchmark,split=args.split,seq_len=args.seq_len)
    external=run_trackeval(staging,trackeval_root=args.trackeval_root,timeout_sec=args.timeout)
    return {'milestone':'C15_T1_P2F','p1_observation_adapter_version':1,
            'research_only':True,'staging':staging,'external_evaluation':external,
            'published_benchmark_gate_passed':False,
            'limitations':['TrackEval source is unauthenticated without separate revision attestation',
              'MOT 2D bounding boxes only: masks require a separate official MOTS adapter',
              'MOTChallenge pedestrian class only: no TAO or BDD100K evaluation implied',
              'No true tracker/DeepSORT/ByteTrack execution occurs in this wrapper',
              'No real learned appearance or genuine sensor confidence certification']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gt',type=Path,required=True)
    p.add_argument('--pred',type=Path,required=True)
    p.add_argument('--staging',type=Path,required=True)
    p.add_argument('--width',type=int,required=True);p.add_argument('--height',type=int,required=True)
    p.add_argument('--sequence',required=True);p.add_argument('--tracker',default='CognitumCandidate')
    p.add_argument('--dataset-id',default='researchfixture');p.add_argument('--dataset-version',default='v1')
    p.add_argument('--gt-source',default='local://gt');p.add_argument('--pred-source',default='local://pred')
    p.add_argument('--benchmark',default='MOT17');p.add_argument('--split',default='train')
    p.add_argument('--seq-len',type=int);p.add_argument('--legacy-gt',action='store_true')
    p.add_argument('--trackeval-root',type=Path);p.add_argument('--timeout',type=int,default=120)
    p.add_argument('--out',type=Path)
    args=p.parse_args()
    report=run(args)
    text=json.dumps(report,sort_keys=True,indent=2)+'\n'
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(text,encoding='utf-8')
    print(text)

if __name__=='__main__':main()
