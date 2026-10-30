"""Synthetic P2V preflight. No calibrated real sensors or authenticated object IDs."""
import argparse
import json
from pathlib import Path

from cognitum.proto import spatial_dynamic_scene_robustness_pb2 as p
from cognitum.spatial_dynamic_scene_robustness import analyze, verify
from tests.test_c15_t3_p2v_dynamic_scene_robustness import fixture, pose_translate


def study():
    def run(name,request):
        result=analyze(request)
        verify(request,result)
        return {
            'name':name, 'request_sha256':result.request_sha256.hex(),
            'p2u_sha256':result.p2u_result_sha256.hex(),
            'poses_disputed':result.pose_discontinuity_found,
            'distinct_frames':len(result.cameras),
            'static_hypothetical_cells':len(result.conservative_static_hypothetical_volume.evidence),
            'camera_discontinuities':sum(x.state==p.P2V_CAMERA_DISCONTINUITY for x in result.cameras),
            'object_states':{x.object_id:p.P2VIdentityState.Name(x.state) for x in result.identities},
            'rejected_static_reasons':{p.P2VStaticState.Name(state):sum(c.state==state for c in result.cells)
                for state in (p.P2V_STATIC_STALE,p.P2V_STATIC_POSE_DISPUTED,
                    p.P2V_STATIC_OBJECT_UNCERTAIN,p.P2V_STATIC_NOT_ELIGIBLE)},
            'no_authority':not result.grants_authority,
        }
    baseline=fixture()
    changed=fixture();pose_translate(changed,.05);changed.max_camera_translation_step_m=.01
    stale=fixture();stale.max_static_age_ticks=1
    stale.dynamic_request.windows[-1].temporal_request.evaluation_tick+=3
    uncertain=fixture();uncertain.reappearance_gap_ticks=30;uncertain.missing_object_exclusion_radius_m=3
    return {'schema':'C15-T3-P2V-synthetic-study-v1','experimental':True,
            'real_3d_sensor_data':False,'baseline':'P2U unchanged',
            'arms':[run('baseline',baseline),run('pose_discontinuity',changed),
                    run('static_staleness',stale),run('reappearance_uncertainty',uncertain)]}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path);args=a.parse_args()
    s=json.dumps(study(),indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(s)
    print(s)
