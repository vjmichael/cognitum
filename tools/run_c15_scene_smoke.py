"""Deterministic C15 research demonstration; not vision or model benchmarking."""
from cognitum import spatial_scene_reference as s
from cognitum.proto import spatial_scene_pb2 as p
import argparse
import json
from pathlib import Path

# This callback is a SYNTHETIC test stub and does not authenticate a Lu host.
TEST_ADMIT = lambda *_: True

def observed(oid, name, point, tick):
    obj=p.SceneObject(object_id=oid,display_name=name,category='prop',frame_id='world',
        visibility=p.VISIBILITY_VISIBLE,confidence=1,observation_source_id='syntheticA',
        last_observed_tick=tick,geometry_ref='synthetic:mesh')
    obj.position_m.x,obj.position_m.y,obj.position_m.z=point
    obj.rotation_xyzw.w=1
    return obj

def command(index,before=None):
    return p.SceneCommand(schema_version=1,scene_id='syntheticScene',conversation_id='syntheticConv',
        trace_id='syntheticTrace',task_id='syntheticTask',request_id=f'req{index}',
        expected_scene_revision=before.revision if before is not None else 0)

def run():
    c=command(1)
    for o in (observed('drone','Drone',(0,0,0),1),
              observed('ship','Derelict',(0.5,0,0),1)):
        m=c.mutations.add(kind=p.MUTATION_OBSERVE,object_id=o.object_id,tick=1)
        m.observed.CopyFrom(o)
    first,receipt=s.apply(None,c,admit=TEST_ADMIT)
    assert s.verify_receipt(None,c,first,receipt,admit=TEST_ADMIT)
    assert any(r.kind==p.RELATION_NEAR_3D for r in first.relations)
    c=command(2,first)
    c.mutations.add(kind=p.MUTATION_OCCLUDE,object_id='drone',expected_object_version=1,tick=2)
    hidden,receipt2=s.apply(first,c,admit=TEST_ADMIT)
    assert s.verify_receipt(first,c,hidden,receipt2,admit=TEST_ADMIT)
    assert len(hidden.relations)==0
    c=command(3,hidden)
    o=observed('drone','Drone',(0.2,0,0),3)
    m=c.mutations.add(kind=p.MUTATION_OBSERVE,object_id='drone',expected_object_version=2,tick=3)
    m.observed.CopyFrom(o)
    returned,receipt3=s.apply(hidden,c,admit=TEST_ADMIT)
    assert s.verify_receipt(hidden,c,returned,receipt3,admit=TEST_ADMIT)
    assert next(o for o in returned.objects if o.object_id=='drone').version==3
    c=command(4,returned);c.conversation_id='otherConv'
    c.mutations.add(kind=p.MUTATION_DELETE,object_id='drone',expected_object_version=3,tick=4)
    denial=''
    try:s.apply(returned,c,admit=TEST_ADMIT)
    except s.SceneRejected as e:denial=str(e)
    assert denial=='SCENE_SCOPE_MISMATCH'
    return {'milestone':'C15 P0-P1 reference','research_only':True,
        'synthetic_test_host_only':True,'real_model_invoked':False,'camera_ingested':False,
        'scene_revisions':[first.revision,hidden.revision,returned.revision],
        'identity_preserved':True,'occlusion_relations_withheld':len(hidden.relations)==0,
        'reappearance_object_version':3,'cross_conversation_denial':denial,
        'receipts_sha256':[x.after_sha256.hex() for x in (receipt,receipt2,receipt3)],
        'external_actions_granted':0}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    evidence=run()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n')
    print(json.dumps(evidence,indent=2,sort_keys=True))

if __name__=='__main__':main()
