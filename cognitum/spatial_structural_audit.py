"""C15/T2+T3 P2: bounded structural/volumetric *consistency*, not reality.

Never infer that an unobserved wall has a solid interior. A caller-supplied
part/void extent remains a claim. A reported measurement is not authenticated.
All coordinates are voxel *indices* in the supplied grid, NOT world geometry.
"""
from __future__ import annotations
from cognitum.proto import spatial_structural_audit_pb2 as p
from cognitum.proto import spatial_volume_pb2 as v
from cognitum.spatial_composition import validate as validate_structure
from cognitum.spatial_volume import classify as classify_volume

class StructuralAuditRejected(ValueError):
    pass

def require(condition: bool, reason: str) -> None:
    if not condition:
        raise StructuralAuditRejected(reason)

def valid_id(s: str) -> bool:
    return isinstance(s, str) and 0 < len(s) <= 128 and all(c.isascii() and (c.isalnum() or c in '_-.:') for c in s)

def audit(graph, grid, request: p.StructuralAuditRequest) -> p.StructuralAuditResult:
    # Original validators independently reject malformed source models.
    nodes, _, _, _ = validate_structure(graph)
    volume = classify_volume(grid)
    require(isinstance(request, p.StructuralAuditRequest)
            and request.schema_version == 1 and request.research_only
            and not request.grants_authority, 'INVALID_RESEARCH_REQUEST')
    require(request.conversation_id == graph.conversation_id == grid.conversation_id
            and request.graph_id == graph.graph_id and request.volume_id == grid.volume_id,
            'CONVERSATION_OR_OBJECT_SCOPE_MISMATCH')
    require(len(request.claims) <= 64 and len(request.SerializeToString()) <= 100_000,
            'RESOURCE_LIMIT')
    result = p.StructuralAuditResult(
        conversation_id=graph.conversation_id, graph_id=graph.graph_id,
        volume_id=grid.volume_id, research_only=True, grants_authority=False)
    by_voxel = {(c.x, c.y, c.z): c for c in volume.cells}
    seen = set()
    budget = 0
    for claim in request.claims:
        require(valid_id(claim.claim_id) and claim.claim_id not in seen,
                'DUPLICATE_OR_INVALID_CLAIM_ID')
        seen.add(claim.claim_id)
        require(claim.node_id in nodes and valid_id(claim.source_ref),
                'MISSING_STRUCTURAL_NODE_OR_PROVENANCE')
        require(claim.expected in (p.SPATIAL_EXPECT_OCCUPIED, p.SPATIAL_EXPECT_FREE),
                'INVALID_EXPECTATION')
        require(claim.HasField('box'), 'MISSING_BOUNDS')
        b = claim.box
        lo = (b.min_x, b.min_y, b.min_z)
        hi = (b.max_x, b.max_y, b.max_z)
        require(all(0 <= a <= c < grid.max_axis for a, c in zip(lo, hi)),
                'INVALID_BOUNDS')
        count = (hi[0]-lo[0]+1)*(hi[1]-lo[1]+1)*(hi[2]-lo[2]+1)
        budget += count
        require(count <= 512 and budget <= 8192, 'REGION_RESOURCE_LIMIT')
        # Semantic type and evidence rank never imply geometry on their own.
        observed, opposite, conflicted, unknown, predicted_only = 0, 0, 0, 0, 0
        target = v.CELL_OCCUPIED if claim.expected == p.SPATIAL_EXPECT_OCCUPIED else v.CELL_FREE
        for x in range(lo[0], hi[0]+1):
            for y in range(lo[1], hi[1]+1):
                for z in range(lo[2], hi[2]+1):
                    cell = by_voxel.get((x,y,z))
                    if cell is None or cell.state == v.CELL_UNKNOWN:
                        unknown += 1
                        if cell is not None and cell.hypothesis_count:
                            predicted_only += 1
                    elif cell.state == v.CELL_CONFLICTED:
                        conflicted += 1
                    elif cell.state == target:
                        observed += 1
                    else:
                        opposite += 1
        # No silent averaging of inconsistent evidence or partial region coverage.
        if conflicted or (observed and opposite):
            status = p.SPATIAL_AUDIT_MIXED
        elif opposite:
            status = p.SPATIAL_AUDIT_CONTRADICTED_BY_CLAIMED_EVIDENCE
        elif observed and not unknown:
            status = p.SPATIAL_AUDIT_CONSISTENT_WITH_CLAIMED_EVIDENCE
        else:
            status = p.SPATIAL_AUDIT_INDETERMINATE
        result.audits.add(claim_id=claim.claim_id, node_id=claim.node_id,
                          state=status, claimed_support_cells=observed,
                          claimed_contradiction_cells=opposite,
                          unresolved_cells=unknown, conflicting_cells=conflicted,
                          predicted_only_cells=predicted_only, total_cells=count)
    result.warnings.extend([
        'INDEX_COORDINATES_NOT_WORLD_FRAME_GEOMETRY',
        'GRAPH_NODE_LABEL_DOES_NOT_PROVE_INTERNAL_STRUCTURE',
        'MEASURED_IS_CALLER_ASSERTED_NOT_AUTHENTICATED',
        'CONSISTENCY_IS_NOT_PHYSICAL_VALIDATION',
        'MIXED_OR_PARTIAL_EVIDENCE_NEVER_AUTO_RESOLVED',
        'NO_ACTION_AUTHORITY',
    ])
    return result
