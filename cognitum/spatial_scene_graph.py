"""C15 derived world-frame scene graph edges; no latent embedding claims.

Only deterministic metric relations computed from validated object poses.
Edges carry source IDs, object versions, and scene epoch so edits invalidate
older derived edges. Axis directions are explicitly world x/y/z, not camera
left/right when a camera has rotated.
"""
from dataclasses import dataclass
from math import dist,isfinite
from .spatial_geometry import Scene,world_position,validate as validate_scene


@dataclass(frozen=True)
class SceneRelation:
    subject_id:str
    predicate:str
    object_id:str
    coordinate_frame:str
    value_m:float
    subject_version:int
    object_version:int
    scene_epoch:int
    evidence_sources:tuple[str,...]
    status:str="derived_not_observed"


def graph_relations(scene:Scene,*,near_m:float=1.0,
                    tolerance_m:float=1e-6)->tuple[SceneRelation,...]:
    validate_scene(scene)
    if (type(near_m) not in (int,float) or not isfinite(near_m)
            or not 0<near_m<=10000
            or type(tolerance_m) not in (int,float)
            or not isfinite(tolerance_m) or not 0<=tolerance_m<=near_m):
        raise ValueError("invalid spatial relation thresholds")
    positions={o.stable_id:world_position(scene,o.stable_id) for o in scene.objects}
    edges=[]
    for a in scene.objects:
        if not a.visible:
            continue
        for b in scene.objects:
            if not b.visible or a.stable_id==b.stable_id:
                continue
            ap=positions[a.stable_id];bp=positions[b.stable_id]
            separation=dist(ap,bp)
            predicates=[]
            if separation<=near_m:
                predicates.append(("near",separation))
            if ap[0]+tolerance_m<bp[0]:
                predicates.append(("world_x_less_than",bp[0]-ap[0]))
            if ap[2]+tolerance_m<bp[2]:
                predicates.append(("world_z_below",bp[2]-ap[2]))
            for predicate,value in predicates:
                edges.append(SceneRelation(
                    a.stable_id,predicate,b.stable_id,"world",
                    value,a.version,b.version,scene.epoch,
                    tuple(sorted({a.observation_source,b.observation_source}))))
    return tuple(edges)


def edge_still_current(scene:Scene,edge:SceneRelation)->bool:
    validate_scene(scene)
    if type(edge) is not SceneRelation or edge.coordinate_frame!="world":
        return False
    if edge.scene_epoch!=scene.epoch:
        return False
    found={o.stable_id:o for o in scene.objects}
    return (edge.subject_id in found and edge.object_id in found
            and found[edge.subject_id].version==edge.subject_version
            and found[edge.object_id].version==edge.object_version
            and found[edge.subject_id].visible and found[edge.object_id].visible)
