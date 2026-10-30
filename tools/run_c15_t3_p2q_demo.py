"""Offline P2Q synthetic camera/depth -> sparse occupancy -> T2 audit smoke."""
import hashlib
import json
from cognitum.proto import spatial_calibrated_depth_pb2 as p
from cognitum.proto import spatial_composition_pb2 as t2
from cognitum.proto import spatial_structural_audit_pb2 as a
from cognitum import spatial_calibrated_depth as depth
from cognitum.spatial_structural_audit import audit


def run():
    q=p.P2QDepthRequest(schema_version=1,conversation_id='demo-chat',volume_id='demo-grid',
                        capture_id='synthetic-capture',voxel_size_m=.5,max_axis=32,
                        evaluation_tick=10,half_life_ticks=5,hit_probability=.8,
                        free_probability=.3,research_only=True)
    cam=q.camera
    cam.frame_id='camera-1';cam.calibration_source_ref='synthetic-claim'
    cam.width=8;cam.height=8;cam.fx=4;cam.fy=4;cam.cx=3.5;cam.cy=3.5
    cam.rectified_pinhole=True;cam.qw=1
    cam.translation.x=cam.translation.y=2;cam.translation.z=1
    cam.max_axial_depth_m=5
    q.camera_sha256=depth._digest(cam)
    digest=hashlib.sha256(b'synthetic-depth-array-not-a-real-camera').digest()
    q.pixels.add(u=3,v=3,axial_depth_m=2.0,tick=10,source_ref='synthetic-depth',
                 depth_frame_sha256=digest,endpoint_hit=True)
    output=depth.project(q)
    assert depth.verify(q,output)
    graph=t2.StructureGraph(schema_version=1,graph_id='proposed-structure',
                            conversation_id='demo-chat',research_only=True)
    graph.nodes.add(node_id='shell',kind='hypothetical-shell',
                    evidence=t2.EVIDENCE_HYPOTHETICAL,source_ref='simulation')
    ar=a.StructuralAuditRequest(schema_version=1,conversation_id='demo-chat',
                                graph_id='proposed-structure',volume_id='demo-grid',
                                research_only=True)
    claim=ar.claims.add(claim_id='claimed-solid',node_id='shell',
                        source_ref='simulation',expected=a.SPATIAL_EXPECT_OCCUPIED)
    claim.box.min_x=claim.box.max_x=4
    claim.box.min_y=claim.box.max_y=4
    claim.box.min_z=claim.box.max_z=6
    t2_result=audit(graph,output.hypothetical_volume,ar)
    outcome={
        'milestone':'C15-T3-P2Q',
        'input_kind':'synthetic_camera_depth',
        'calibration_authenticated':False,
        'sensor_authenticated':False,
        'research_only':output.research_only,
        'grants_authority':output.grants_authority,
        'request_sha256':output.request_sha256.hex(),
        'camera_sha256':output.camera_sha256.hex(),
        'projected':len(output.projections),
        'first_world_endpoint_m':[output.projections[0].world_endpoint_m.x,
                                  output.projections[0].world_endpoint_m.y,
                                  output.projections[0].world_endpoint_m.z],
        'first_endpoint_voxel':[output.projections[0].voxel_x,
                                output.projections[0].voxel_y,
                                output.projections[0].voxel_z],
        'occupancy_cells':len(output.temporal_result.cells),
        'hypothetical_volume_cells':len(output.hypothetical_volume.evidence),
        't2_assessment':a.SpatialAuditState.Name(t2_result.audits[0].state),
        't2_predicted_only':t2_result.audits[0].predicted_only_cells,
        'warnings':list(output.warnings),
    }
    assert outcome['t2_assessment']=='SPATIAL_AUDIT_INDETERMINATE'
    return outcome


if __name__=='__main__':
    print(json.dumps(run(),indent=2,sort_keys=True))
