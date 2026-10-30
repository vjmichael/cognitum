"""C15/T1 P2E diagnostic for a real annotated MOT sequence (research only).

Does NOT run DeepSORT, ByteTrack or a real detector, and never treats
GT identities as permitted tracker input. Dataset files are NOT bundled.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from cognitum.spatial_mot_adapter import read_mot, evaluate, MOTRejected

PINNED_TUD = {
    "gt": {"path": "motmetrics/data/TUD-Campus/gt.txt", "git_blob_sha1": "182d09a1683b0e87349b00661d9cdcc1ffaf39df", "rows": 359},
    "prediction": {"path": "motmetrics/data/TUD-Campus/test.txt", "git_blob_sha1": "64b0fe10e177ea92dd9bbe0e9385d721edb33982", "rows": 222},
}
SOURCE_REPO = "https://github.com/cheind/py-motmetrics"


def git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


def run(gt_path: str | Path, prediction_path: str | Path, *, pin_tud: bool = True):
    if Path(gt_path).resolve() == Path(prediction_path).resolve():
        raise MOTRejected('INPUT_ROLES_MUST_BE_DISTINCT')
    # MOT15/TUD public fixture uses -1 for unspecified class and visibility.
    # Its positive GT boxes represent pedestrian targets; the strict MOT17
    # reader correctly rejects those sentinel values as invalid visibility.
    # For pinned TUD only, parse as detections then use the original GT IDs.
    gt,gt_sha=read_mot(gt_path,kind='det' if pin_tud else 'gt')
    pred,pred_sha=read_mot(prediction_path,kind='prediction')
    blobs={'gt':git_blob_id(Path(gt_path).read_bytes()), 'prediction':git_blob_id(Path(prediction_path).read_bytes())}
    if pin_tud and any(blobs[key] != value['git_blob_sha1'] for key,value in PINNED_TUD.items()):
        raise MOTRejected('SOURCE_GIT_BLOB_MISMATCH')
    if pin_tud and (len(gt)!=359 or len(pred)!=222):
        raise MOTRejected('PINNED_ROW_COUNT_MISMATCH')
    diagnostic=evaluate(gt,pred)
    return {
        'milestone':'C15_T1_P2E', 'research_only':True,
        'external_data_verified_to_pinned_blob':bool(pin_tud),
        'source_repository':SOURCE_REPO, 'fixture':'TUD-Campus' if pin_tud else 'user_supplied_MOT',
        'input_sha256': {'gt':gt_sha,'prediction':pred_sha},
        'input_git_blob_sha1':blobs,
        'frames_gt':len({b.frame for b in gt}),
        'gt_ids':len({b.track_id for b in gt}),
        'gt_boxes':len(gt), 'prediction_boxes':len(pred),
        'diagnostic':diagnostic,
        'official_motchallenge_metrics':False,
        'deep_sort_executed':False, 'byte_track_executed':False,
        'learned_visual_features':False,
        'limitations':[
           'Original video frames and pretrained appearance weights not provided',
           'Reference test.txt is NOT a DeepSORT or ByteTrack output',
           'Custom IoU/identity diagnostics can differ from official MOTChallenge evaluation',
           'Official TrackEval or motmetrics run required before published benchmark claims',
           'No user actions authorized by these offline research calculations',
        ],
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--gt',required=True)
    ap.add_argument('--pred',required=True)
    ap.add_argument('--out',type=Path)
    ap.add_argument('--no-pin',action='store_true',help='Allow different MOT-format files, still report provenance')
    a=ap.parse_args()
    rec=run(a.gt,a.pred,pin_tud=not a.no_pin)
    txt=json.dumps(rec,indent=2,sort_keys=True)+'\n'
    if a.out:
        a.out.parent.mkdir(exist_ok=True,parents=True)
        a.out.write_text(txt)
    print(txt)

if __name__=='__main__':main()
