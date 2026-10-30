"""P2D research preflight for real annotated MOTChallenge sequences.

Example:
  python tools/c15_tracking_preflight.py --gt /datasets/MOT17/train/MOT17-02-FRCNN/gt/gt.txt \
     --det /datasets/MOT17/train/MOT17-02-FRCNN/det/det.txt \
     --deep-sort /results/deepsort.txt --byte-track /results/bytetrack.txt

Does not run trackers; refuses to synthesize detections from GT. Reports only
input completeness and separate track-output diagnostics when all files exist.
"""
import argparse,json
from pathlib import Path
from cognitum.spatial_mot_adapter import read_mot,evaluate,MOTRejected

def main():
 p=argparse.ArgumentParser();p.add_argument('--gt',required=True);p.add_argument('--det',required=True)
 p.add_argument('--deep-sort');p.add_argument('--byte-track');p.add_argument('--cognitum');p.add_argument('--out')
 a=p.parse_args()
 result={'research_only':True,'official_motchallenge_benchmark':False,'real_annotated_sequence_available':False,
         'trusted_128d_embeddings_available':False,'original_tracker_outputs_available':False,
         'comparisons':{},'limitations':['requires frames and image-derived learned descriptors','no official TrackEval HOTA/MOTA certification']}
 for role,path in [('gt',a.gt),('det',a.det)]:
  if not Path(path).is_file():
   result['missing_'+role]=str(path)
  else:
   rows,digest=read_mot(path,kind=role);result[role]={'rows':len(rows),'sha256':digest};
 if 'gt' in result and 'det' in result:
  result['real_annotated_sequence_available']=True
  result['original_tracker_outputs_available']=bool(a.deep_sort and a.byte_track and Path(a.deep_sort).is_file() and Path(a.byte_track).is_file())
  for key,path in [('DeepSORT',a.deep_sort),('ByteTrack',a.byte_track),('Cognitum',a.cognitum)]:
   if path and Path(path).is_file():
    rows,digest=read_mot(path,kind='prediction');result['comparisons'][key]={'sha256':digest,**evaluate(read_mot(a.gt,kind='gt')[0],rows)}
 payload=json.dumps(result,sort_keys=True,indent=2)
 if a.out:Path(a.out).write_text(payload)
 print(payload)
 return 0 if result['real_annotated_sequence_available'] else 2
if __name__=='__main__':raise SystemExit(main())
