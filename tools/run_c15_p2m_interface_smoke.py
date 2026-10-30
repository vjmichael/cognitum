"""C15 P2M self-contained deterministic synthetic interface and handoff smoke.

No external downloads, no GT identities, no real MOT17 measurements.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
from PIL import Image, ImageDraw
from cognitum.spatial_p2k_dense_identity import Detection
from cognitum.spatial_p2m_pipeline import build_request_from_frames, research_pipeline


def run():
    images={};boxes={}
    for frame,x in ((1,8),(2,12),(3,16)):
        image=Image.new('RGB',(96,64),(22,22,22))
        draw=ImageDraw.Draw(image)
        draw.rectangle((x,10,x+20,34),fill=(210,45,190))
        out=io.BytesIO();image.save(out,format='PNG')
        images[frame]=out.getvalue()
        boxes[frame]=[Detection(frame,x,10,21,25)]
    req=build_request_from_frames(conversation_id='p2m.demo',sequence_id='synthetic.1',
      request_id='p2m.smoke',image_bytes=images,boxes=boxes)
    desc,handoff,counts=research_pipeline(req)
    return {'status':'synthetic_interface_smoke_passed','metric_is_official':False,
      'real_video_metrics':None,'model_backend':'pinned_handcrafted_histogram_cpu',
      'frame_count':len(desc.frames),'candidate_count':len(handoff.candidates),
      'hypothetical_t2_nodes':len(handoff.t2_hypothetical_graph.nodes),
      't2_edges':len(handoff.t2_hypothetical_graph.edges),
      't3_projection_blocked':handoff.t3_projection_blocked_without_calibration,
      'canonical_scene_mutation_blocked':handoff.canonical_scene_mutation_blocked,
      'no_action_authority':not handoff.grants_authority,
      'source_request_sha256':desc.request_sha256.hex(),
      'handoff_sha256':hashlib.sha256(handoff.SerializeToString(deterministic=True)).hexdigest(),
      'counts':counts}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();out=run();payload=json.dumps(out,sort_keys=True,indent=2)+'\n'
    if args.output:args.output.write_text(payload)
    else:print(payload)

if __name__=='__main__':main()
