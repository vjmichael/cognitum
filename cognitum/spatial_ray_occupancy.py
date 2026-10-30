"""C15 T3 P2B: bounded sparse 3D DDA ray integration and conservative block summaries.

Caller assertions, NOT authenticated lidar/sensors. Binary log odds assume independent
observations and calibrated inverse sensor models; neither is validated here.
"""
from __future__ import annotations
from collections import defaultdict
import math
from cognitum.proto import ray_occupancy_pb2 as pb

class RayRejected(ValueError):
    pass

def require(ok, why):
    if not ok:raise RayRejected(why)

def _no_unknown(message):
    canonical=type(message)()
    canonical.CopyFrom(message)
    canonical.DiscardUnknownFields()
    return canonical==message

def ident(s):
    return isinstance(s,str) and 0<len(s)<=128 and all(c.isascii() and (c.isalnum() or c in '_-.:') for c in s)

def _dda(start,end,res,max_axis,include_endpoint_cell=True):
    a=[x/res for x in start];b=[x/res for x in end]
    direction=[b[i]-a[i] for i in range(3)]
    step=[(1 if x>0 else -1 if x<0 else 0) for x in direction]
    # Half-open cells: a ray departing a *precise* grid plane in the
    # negative direction enters the cell below it. The cell above the
    # plane has zero traversed length and must not receive free evidence.
    # Do not use epsilon-near-boundary snapping: slightly-inside points
    # belong to their actual starting cell.
    cell=[math.floor(a[i])-(1 if step[i]<0 and a[i].is_integer() else 0)
          for i in range(3)]
    # Traverse only positive-length segment interiors. When a ray ends
    # exactly on a positive-going grid plane, the endpoint belongs to
    # the next half-open cell, but the interior does not. Append the
    # endpoint cell once after completing the interior traversal; this
    # also avoids floating-point tie errors at t == 1 on multiple axes.
    endpoint=[math.floor(x) for x in b]
    target=[endpoint[i]-(1 if step[i]>0 and b[i].is_integer() else 0)
            for i in range(3)]
    delta=[abs(1/d) if d else math.inf for d in direction]
    next_t=[((cell[i]+(1 if step[i]>0 else 0)-a[i])/direction[i]) if direction[i] else math.inf for i in range(3)]
    cells=[]
    for _ in range(max_axis*3+3):
        require(all(0<=v<max_axis for v in cell),'RAY_TRAVERSAL_OUT_OF_BOUNDS')
        cells.append(tuple(cell))
        if cell==target:
            if include_endpoint_cell and endpoint!=cell:
                require(all(0<=v<max_axis for v in endpoint),'RAY_TRAVERSAL_OUT_OF_BOUNDS')
                cells.append(tuple(endpoint))
            return cells
        t=min(next_t)
        require(math.isfinite(t) and t<=1+1e-10,'INVALID_RAY_TRAVERSAL')
        # Exact tie: step all touched axes; do not mark boundary-only neighbors.
        for i in range(3):
            if next_t[i]<=t+1e-12:
                cell[i]+=step[i];next_t[i]+=delta[i]
    raise RayRejected('RAY_STEP_LIMIT')

def _prob(lod):
    return 1/(1+math.exp(-lod))

def integrate(batch:pb.RayBatch)->pb.RayResearchResult:
    require(isinstance(batch,pb.RayBatch) and batch.schema_version==1 and batch.research_only and not batch.grants_authority,'INVALID_RESEARCH_CONTRACT')
    require(_no_unknown(batch),'UNKNOWN_PROTO_FIELDS')
    require(ident(batch.volume_id) and ident(batch.conversation_id) and math.isfinite(batch.voxel_size_m) and .001<=batch.voxel_size_m<=1000 and 1<=batch.max_axis<=128,'INVALID_GRID_SCOPE')
    require(1<=len(batch.rays)<=256 and len(batch.SerializeToString())<=150_000,'RESOURCE_LIMIT')
    updates={};source_ticks=set()
    max_coord=batch.voxel_size_m*batch.max_axis
    for ray in batch.rays:
        require(ray.HasField('start') and ray.HasField('end') and ident(ray.source_ref) and ray.tick>0,'UNPROVENANCED_RAY')
        start=(ray.start.x,ray.start.y,ray.start.z);end=(ray.end.x,ray.end.y,ray.end.z)
        require(all(math.isfinite(p) and 0<=p<max_coord for p in start+end),'INVALID_RAY_POINT')
        require(any(abs(start[i]-end[i])>1e-12 for i in range(3)),'ZERO_LENGTH_RAY')
        require(all(math.isfinite(p) for p in (ray.hit_probability,ray.free_probability)) and .5<ray.hit_probability<.999 and .001<ray.free_probability<.5,'INVALID_SENSOR_MODEL')
        cells=_dda(start,end,batch.voxel_size_m,batch.max_axis,
                   include_endpoint_cell=ray.endpoint_hit)
        require(len(cells)<=4096,'RAY_CELL_LIMIT')
        for i,cell in enumerate(cells):
            is_hit=ray.endpoint_hit and i==len(cells)-1
            key=(ray.source_ref,ray.tick,cell)
            outcome=1 if is_hit else -1
            prev=updates.get(key)
            require(prev is None or prev[0]==outcome,'SAME_SOURCE_SAME_TICK_CONFLICT')
            if prev is None:updates[key]=(outcome,ray.hit_probability if is_hit else ray.free_probability)
            else:
                require(abs(prev[1]-(ray.hit_probability if is_hit else ray.free_probability))<1e-12,'SAME_SOURCE_SAME_TICK_SENSOR_MISMATCH')
        source_ticks.add((ray.source_ref,ray.tick))
    require(len(updates)<=16384,'SPARSE_CELL_RESOURCE_LIMIT')
    grouped=defaultdict(list)
    for (source,tick,cell),value in updates.items():grouped[cell].append((source,tick,*value))
    result=pb.RayResearchResult(volume_id=batch.volume_id,conversation_id=batch.conversation_id,research_only=True,grants_authority=False)
    cell_map={}
    for coord, entries in sorted(grouped.items()):
        hit=sum(e[2]==1 for e in entries);free=sum(e[2]==-1 for e in entries)
        lod=sum(math.log(p/(1-p)) for _src,_tick,_sgn,p in entries)
        lod=max(-8.,min(8.,lod))
        cell=result.cells.add(x=coord[0],y=coord[1],z=coord[2],measured_log_odds=lod,hit_count=hit,free_count=free,source_refs=sorted({x[0] for x in entries}),conflicted=bool(hit and free))
        cell_map[coord]=cell
    for scale in (2,4):
        blocks=defaultdict(list)
        for xyz,cell in cell_map.items():blocks[tuple(x//scale for x in xyz)].append(cell)
        for key,cells in sorted(blocks.items()):
            # Edge blocks on non-divisible grids have fewer expected children.
            expected=math.prod(min(scale,batch.max_axis-k*scale) for k in key)
            complete=len(cells)==expected
            states=[0 if c.conflicted or abs(c.measured_log_odds)<.1 else (1 if c.measured_log_odds>0 else -1) for c in cells]
            result.coarse_blocks.add(level=scale,x=key[0],y=key[1],z=key[2],observed_children=len(cells),expected_children=expected,complete=complete,mean_probability=(sum(_prob(c.measured_log_odds) for c in cells)/len(cells) if complete else 0.),mixed_states=0 in states or len(set(states))>1)
    if any(c.conflicted for c in result.cells):result.warnings.append('CONTRADICTORY_RAY_MEASUREMENTS_RETAINED')
    result.warnings.extend(['UNOBSERVED_VOXELS_REMAIN_UNKNOWN','INCOMPLETE_COARSE_BLOCK_NOT_CLASSIFIED','INVERSE_SENSOR_PROBABILITIES_NOT_CALIBRATED','CORRELATED_RAYS_MAY_OVERSTATE_CONFIDENCE','CALLER_SUPPLIED_RAYS_NOT_AUTHENTICATED','NO_ACTION_AUTHORITY'])
    return result
