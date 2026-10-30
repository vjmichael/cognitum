"""C15 P2T deterministic depth-to-object-to-structure research smoke."""
import json
from cognitum.spatial_object_aware_volume import analyze,verify
from cognitum.proto import spatial_object_aware_volume_pb2 as p
from tests.test_c15_t3_p2t_object_aware_volume import fixture,OLD,NEW,getcell

def run():
    req=fixture()
    result=analyze(req)
    assert verify(req,result)
    def item(coord):
        cell=getcell(result,coord)
        return dict(voxel=list(coord),temporal_state=cell.temporal_state,
            explanation=p.P2TCellExplanation.Name(cell.explanation),
            object_ids=list(cell.candidate_object_ids),static_handoff_allowed=cell.static_handoff_allowed)
    return dict(milestone='C15 T3 P2T',research_only=result.research_only,
        grants_authority=result.grants_authority,
        request_sha256=result.request_sha256.hex(),
        scene_sha256=result.scene_sha256.hex(),
        source_capture_count=len(req.temporal_request.captures),
        moving_object_count=len(req.tracks),
        motion_candidate_count=len(result.motion_candidates),
        origin=item(OLD),destination=item(NEW),
        stationary_hypothetical_voxel_count=len(result.stationary_hypothetical_volume.evidence),
        warnings=list(result.warnings))

if __name__=='__main__':print(json.dumps(run(),indent=2,sort_keys=True))
