"""Evaluate controlled synthetic-image crossing, not real pedestrian ReID.

Synthetic identity labels exist only in this experiment's scoring loop, never
in the association inputs or descriptor construction. No official MOT score.
"""
from __future__ import annotations
import io
import json
from PIL import Image, ImageDraw
from cognitum.spatial_p2k_dense_identity import Detection,assign_all
from cognitum.spatial_p2l_appearance import descriptors_from_frames,assign_with_appearance

SEQ='C15-P2L-CONTROLLED'

def run():
    scenarios={
      'crossing_constant_speed': [[0,100],[30,70],[60,40],[90,10]],
      'crossing_accelerated': [[0,100],[20,80],[65,35],[100,0]],
      'indistinguishable_appearance': [[0,100],[20,80],[65,35],[100,0]],
    }
    report=[]
    for name,positions in scenarios.items():
        frames={};images={}
        for f,coordinates in enumerate(positions,1):
            im=Image.new('L',(180,40),128);draw=ImageDraw.Draw(im)
            frames[f]=[Detection(f,x,10,12,12) for x in coordinates]
            values=(240,40) if name!='indistinguishable_appearance' else (180,180)
            for x,val in zip(coordinates,values):draw.rectangle((x,10,x+11,21),fill=val)
            b=io.BytesIO();im.save(b,format='PNG');images[f]=b.getvalue()
        specs=descriptors_from_frames(frames,images,sequence=SEQ)
        modes={mode:assign_all(frames,num_frames=len(positions),mode=mode)[0]
               for mode in ('position','velocity')}
        modes['appearance_velocity']=assign_with_appearance(frames,num_frames=len(positions),
            sequence=SEQ,image_bytes=images,descriptors=specs)[0]
        # Score mapping consistency with object A/B across all frames.
        # ID names are arbitrary; compare each object's ID to its first ID.
        retained={key:sum(value[f][i]==value[1][i] for f in value for i in range(2))
                   for key,value in modes.items()}
        report.append({'scenario':name,'frames':len(positions),'box_count':len(positions)*2,
                       'id_consistency_correct_over_8':retained,'research_only':True,
                       'external_mot17_scores':None,'identity_labels_used_for_association':False})
    return {'milestone':'C15_P2L_SYNTHETIC_IMAGE_ABLATIONS','scenarios':report,
            'do_not_claim_real_reid_or_mot17_improvement':True}

if __name__=='__main__':print(json.dumps(run(),sort_keys=True,indent=2))
