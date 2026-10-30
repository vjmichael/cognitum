"""C15/T3 bounded sparse voxels; observations not authenticated or calibrated.

Measured evidence is distinguished from hypothetical occupation. A hypothetical
solid interior cannot be silently converted into an observed solid interior.
"""
from __future__ import annotations
from collections import defaultdict
import math
from cognitum.proto import spatial_volume_pb2 as pb

class VolumeRejected(ValueError): pass

def _require(ok, why):
    if not ok:raise VolumeRejected(why)

def _valid_id(s):return s and len(s)<=128 and all(x.isascii() and (x.isalnum() or x in '_-.:') for x in s)

def classify(grid:pb.VolumeGrid)->pb.VolumeResult:
    _require(isinstance(grid,pb.VolumeGrid) and grid.schema_version==1 and grid.research_only and not grid.grants_authority,'INVALID_CONTRACT')
    _require(_valid_id(grid.volume_id) and _valid_id(grid.conversation_id),'SCOPE_MISMATCH')
    _require(math.isfinite(grid.voxel_size_m) and .001<=grid.voxel_size_m<=1000 and 1<=grid.max_axis<=128,'INVALID_GRID')
    _require(len(grid.evidence)<=8192 and len(grid.SerializeToString())<=500_000,'RESOURCE_LIMIT')
    unique=set(); grouped=defaultdict(dict)
    for ev in grid.evidence:
        _require(all(0<=v<grid.max_axis for v in (ev.x,ev.y,ev.z)),'OUT_OF_BOUNDS')
        _require(ev.kind in (pb.VOLUME_MEASURED_FREE,pb.VOLUME_MEASURED_OCCUPIED,pb.VOLUME_PREDICTED_FREE,pb.VOLUME_PREDICTED_OCCUPIED),'INVALID_EVIDENCE_KIND')
        _require(_valid_id(ev.source_id) and ev.tick>0 and math.isfinite(ev.reliability) and .5<=ev.reliability<=.999,'INVALID_EVIDENCE_PROVENANCE')
        key=(ev.x,ev.y,ev.z,ev.source_id,ev.tick)
        _require(key not in unique,'REPEATED_VOXEL_OBSERVATION');unique.add(key)
        previous=grouped[(ev.x,ev.y,ev.z)].get(ev.source_id)
        if previous is None or ev.tick>previous.tick:grouped[(ev.x,ev.y,ev.z)][ev.source_id]=ev
    result=pb.VolumeResult(volume_id=grid.volume_id,conversation_id=grid.conversation_id,research_only=True,grants_authority=False)
    conflicts=0
    for cell, evidence_by_source in sorted(grouped.items()):
        evidence=list(evidence_by_source.values())
        measured=[e for e in evidence if e.kind in (pb.VOLUME_MEASURED_FREE,pb.VOLUME_MEASURED_OCCUPIED)]
        hypotheses=len(evidence)-len(measured)
        pos=sum(e.kind==pb.VOLUME_MEASURED_OCCUPIED for e in measured)
        neg=sum(e.kind==pb.VOLUME_MEASURED_FREE for e in measured)
        if pos and neg:state=pb.CELL_CONFLICTED;conflicts+=1
        elif pos:state=pb.CELL_OCCUPIED
        elif neg:state=pb.CELL_FREE
        else:state=pb.CELL_UNKNOWN
        lod=sum((1 if e.kind==pb.VOLUME_MEASURED_OCCUPIED else -1)*math.log(e.reliability/(1-e.reliability)) for e in measured)
        result.cells.add(x=cell[0],y=cell[1],z=cell[2],state=state,measured_log_odds=lod,hypothesis_count=hypotheses,source_ids=sorted(evidence_by_source))
    if conflicts:result.warnings.append('CONTRADICTORY_MEASUREMENTS_REQUIRE_REVIEW')
    result.warnings.extend(['UNLISTED_CELLS_REMAIN_UNKNOWN','NO_OCCUPANCY_FROM_PREDICTION_ONLY','MEASURED_IS_CALLER_ASSERTION_NOT_AUTHENTICATION','LOG_ODDS_NOT_CALIBRATED_CONFIDENCE','NO_ACTION_AUTHORITY'])
    return result

def lookup(result:pb.VolumeResult,x:int,y:int,z:int)->int:
    for c in result.cells:
        if (c.x,c.y,c.z)==(x,y,z):return c.state
    return pb.CELL_UNKNOWN
