"""P2U offline reproducibility demonstrator: synthetic captures only."""
import argparse
import json
from pathlib import Path
from cognitum.spatial_dynamic_scene_mapping import map_scene, verify
from cognitum.proto import spatial_dynamic_scene_mapping_pb2 as p
from tests.test_c15_t3_p2u_dynamic_scene_mapping import request


def run():
    q = request()
    result = map_scene(q)
    verify(q,result)
    return dict(schema='C15-T3-P2U-v1', research_only=True, real_sensor_data=False,
        source='synthetic P2T/P2S depth capture fixture',
        request_sha256=result.request_sha256.hex(),
        window_result_sha256=[h.hex() for h in result.p2t_result_sha256],
        unique_captures=result.unique_capture_count,
        objects=[{'id':r.object_id,'state':p.P2UObjectState.Name(r.state),
                  'distinct_motion_windows':r.distinct_motion_windows,
                  'unique_motion_links':r.distinct_motion_links} for r in result.objects],
        voxel_states={p.P2UVoxelState.Name(v):sum(c.state==v for c in result.cells)
                      for v in (p.P2U_STATIC_HYPOTHESIS,p.P2U_DYNAMIC_HYPOTHESIS,
                      p.P2U_RECENTLY_DYNAMIC,p.P2U_CONTESTED,p.P2U_UNKNOWN)},
        static_handoff_cells=len(result.stationary_hypothetical_volume.evidence),
        no_authority=not result.grants_authority,
        warnings=list(result.warnings))

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    data=json.dumps(run(),indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(data)
    print(data)
