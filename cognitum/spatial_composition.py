"""C15/T2 finite typed mereology graph; read-only research reference.

All labels and evidence origins are claims supplied by callers. A claimed
observation is not an authenticated measurement; no host authority is created.
"""
from __future__ import annotations
from collections import defaultdict
from cognitum.proto import spatial_composition_pb2 as pb

class StructureRejected(ValueError): pass

def _require(ok, why):
    if not ok: raise StructureRejected(why)

def _valid_id(x): return isinstance(x,str) and 0<len(x)<=128 and all(c.isascii() and (c.isalnum() or c in '_-.:') for c in x)

def validate(graph:pb.StructureGraph):
    _require(isinstance(graph,pb.StructureGraph) and graph.schema_version==1 and graph.research_only and not graph.grants_authority,'INVALID_RESEARCH_CONTRACT')
    _require(_valid_id(graph.graph_id) and _valid_id(graph.conversation_id),'INVALID_SCOPE')
    _require(len(graph.nodes)<=256 and len(graph.edges)<=512 and len(graph.SerializeToString())<=100_000,'RESOURCE_LIMIT')
    nodes={}
    for node in graph.nodes:
        _require(_valid_id(node.node_id) and 0<len(node.kind)<=96 and len(node.description)<=512,'INVALID_NODE')
        _require(node.node_id not in nodes,'DUPLICATE_NODE')
        _require(node.evidence in (pb.EVIDENCE_OBSERVED,pb.EVIDENCE_INFERRED,pb.EVIDENCE_HYPOTHETICAL),'INVALID_EVIDENCE')
        _require(_valid_id(node.source_ref),'UNPROVENANCED_NODE')
        nodes[node.node_id]=node
    parents={}; children=defaultdict(set); connections=defaultdict(dict); seen=set()
    for edge in graph.edges:
        _require(edge.from_id in nodes and edge.to_id in nodes and edge.from_id!=edge.to_id,'INVALID_EDGE_ENDPOINT')
        _require(edge.relation in (pb.STRUCTURE_PART_OF,pb.STRUCTURE_CONNECTED_TO,pb.STRUCTURE_CONTAINS),'INVALID_EDGE_TYPE')
        _require(edge.evidence in (pb.EVIDENCE_OBSERVED,pb.EVIDENCE_INFERRED,pb.EVIDENCE_HYPOTHETICAL) and _valid_id(edge.source_ref),'INVALID_EDGE_EVIDENCE')
        # Observed edge cannot attach hypothetical node as an asserted fact.
        if edge.evidence==pb.EVIDENCE_OBSERVED:
            _require(nodes[edge.from_id].evidence!=pb.EVIDENCE_HYPOTHETICAL and nodes[edge.to_id].evidence!=pb.EVIDENCE_HYPOTHETICAL,'OBSERVATION_HYPOTHESIS_CONFLATION')
        if edge.relation==pb.STRUCTURE_CONNECTED_TO:
            a,b=sorted((edge.from_id,edge.to_id));key=(a,b,'connection')
            _require(key not in seen,'DUPLICATE_EDGE');seen.add(key)
            connections[a][b]=edge;connections[b][a]=edge
        else:
            child,parent=(edge.from_id,edge.to_id) if edge.relation==pb.STRUCTURE_PART_OF else (edge.to_id,edge.from_id)
            key=(child,parent,'part');_require(key not in seen,'DUPLICATE_EDGE');seen.add(key)
            _require(child not in parents,'MULTIPLE_STRUCTURAL_PARENTS')
            parents[child]=(parent,edge);children[parent].add(child)
    for ident in nodes:
        visited=set();cur=ident
        while cur in parents:
            _require(cur not in visited,'PART_WHOLE_CYCLE');visited.add(cur);cur=parents[cur][0]
    return nodes,parents,children,connections

def query(graph:pb.StructureGraph, request:pb.StructureQuery)->pb.StructureAnswer:
    nodes,parents,children,connections=validate(graph)
    _require(isinstance(request,pb.StructureQuery) and request.schema_version==1 and request.graph_id==graph.graph_id and request.conversation_id==graph.conversation_id,'SCOPE_MISMATCH')
    _require(request.target_id in nodes,'UNKNOWN_TARGET')
    ans=pb.StructureAnswer(target_id=request.target_id,research_only=True,grants_authority=False)
    def admitted(n):return request.include_hypotheses or nodes[n].evidence!=pb.EVIDENCE_HYPOTHETICAL
    if not admitted(request.target_id):
        ans.warnings.append('HYPOTHETICAL_TARGET_NOT_ADMITTED');return ans
    cur=request.target_id
    while cur in parents:
        parent,edge=parents[cur]
        if (edge.evidence==pb.EVIDENCE_HYPOTHETICAL or not admitted(parent)) and not request.include_hypotheses:break
        ans.ancestors.append(parent);cur=parent
    def walk(n):
        for child in sorted(children[n]):
            edge=parents[child][1]
            if admitted(child) and (request.include_hypotheses or edge.evidence!=pb.EVIDENCE_HYPOTHETICAL):
                ans.descendants.append(child);walk(child)
    walk(request.target_id)
    ans.connections.extend(sorted(c for c,e in connections[request.target_id].items() if admitted(c) and (request.include_hypotheses or e.evidence!=pb.EVIDENCE_HYPOTHETICAL)))
    if any(n.evidence!=pb.EVIDENCE_OBSERVED for n in nodes.values()) or any(e.evidence!=pb.EVIDENCE_OBSERVED for e in graph.edges):
        ans.warnings.append('MIXED_OBSERVED_INFERRED_HYPOTHETICAL_CONTENT')
    ans.warnings.extend(['CALLER_SUPPLIED_EVIDENCE_NOT_AUTHENTICATED','NO_INTERNAL_STRUCTURE_INFERRED_FROM_SURFACE_ALONE','NO_ACTION_AUTHORITY'])
    return ans
