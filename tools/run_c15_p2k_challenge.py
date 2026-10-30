"""Execute fixed C15 P2K full-sequence ID-blind MOT17 challenge."""
import argparse
import json
from pathlib import Path
from cognitum.spatial_p2k_challenge_gate import stage,evaluate

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for opt in ('data-zip','labels-zip','stage','trackeval-root','source-zip','out'):
        ap.add_argument('--'+opt,type=Path,required=True)
    a=ap.parse_args()
    a.data_zip=a.data_zip.resolve()
    a.labels_zip=a.labels_zip.resolve()
    a.stage=a.stage.resolve()
    a.trackeval_root=a.trackeval_root.resolve()
    a.source_zip=a.source_zip.resolve()
    report=stage(data_zip=a.data_zip,labels_zip=a.labels_zip,out_dir=a.stage)
    report['official_evaluation']=evaluate(out_dir=a.stage,evidence=report,
                                            trackeval_root=a.trackeval_root,source_zip=a.source_zip,timeout=600)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'complete','summary':report['official_evaluation']['scores'],
                      'sequences':[(r['sequence'],r['input_boxes']) for r in report['sequences']]},sort_keys=True))

if __name__=='__main__': main()
