"""C15 T2 P2B: bounded, read-only assembly/mereology/functional claim audit.

Separate this multi-parent assembly model from P1's single-parent scene ontology.
Claims are supplied by callers; even 'OBSERVED' does not authenticate a sensor.
"""
from __future__ import annotations
from collections import defaultdict
from cognitum.proto import assembly_pb2 as pb

class AssemblyRejected(ValueError):
    pass

def require(ok, reason):
    if not ok:
        raise AssemblyRejected(reason)

def _no_unknown(message):
    canonical=type(message)()
    canonical.CopyFrom(message)
    canonical.DiscardUnknownFields()
    return canonical==message

def ident(s):
    return isinstance(s, str) and 0 < len(s) <= 128 and all(c.isascii() and (c.isalnum() or c in "_-.:") for c in s)

def evidence(e):
    return e in (pb.ASSEMBLY_OBSERVED, pb.ASSEMBLY_INFERRED, pb.ASSEMBLY_HYPOTHETICAL)

def analyze(request: pb.AssemblyResearchRequest) -> pb.AssemblyResearchResult:
    require(isinstance(request,pb.AssemblyResearchRequest) and request.schema_version==1 and request.research_only and not request.grants_authority,'INVALID_RESEARCH_CONTRACT')
    require(_no_unknown(request),'UNKNOWN_PROTO_FIELDS')
    require(ident(request.graph_id) and ident(request.conversation_id),'INVALID_SCOPE')
    require(len(request.objects)<=256 and len(request.memberships)<=512 and len(request.requirements)<=256 and len(request.absences)<=256 and len(request.functions)<=256 and len(request.SerializeToString())<=120_000,'RESOURCE_LIMIT')
    objects={}
    for obj in request.objects:
        require(ident(obj.id) and ident(obj.kind) and ident(obj.source_ref) and evidence(obj.evidence),'INVALID_OBJECT')
        require(obj.id not in objects,'DUPLICATE_OBJECT')
        objects[obj.id]=obj
    graph=defaultdict(set); groups=defaultdict(list); seen=set()
    for m in request.memberships:
        require(m.part_id in objects and m.assembly_id in objects and m.part_id!=m.assembly_id and ident(m.role) and ident(m.source_ref) and evidence(m.evidence),'INVALID_MEMBERSHIP')
        require((m.part_id,m.assembly_id,m.role) not in seen,'DUPLICATE_MEMBERSHIP')
        seen.add((m.part_id,m.assembly_id,m.role))
        if m.evidence==pb.ASSEMBLY_OBSERVED:
            require(objects[m.part_id].evidence!=pb.ASSEMBLY_HYPOTHETICAL and objects[m.assembly_id].evidence!=pb.ASSEMBLY_HYPOTHETICAL,'OBSERVATION_HYPOTHESIS_CONFLATION')
        graph[m.part_id].add(m.assembly_id)
        groups[(m.assembly_id,m.role)].append(m)
    # A part may belong to multiple distinct assemblies, but membership cycles are impossible.
    visiting=set();done=set()
    def visit(node):
        if node in visiting: raise AssemblyRejected('PART_WHOLE_CYCLE')
        if node in done:return
        visiting.add(node)
        for parent in sorted(graph[node]):visit(parent)
        visiting.remove(node);done.add(node)
    for node in objects:visit(node)
    required={}
    for r in request.requirements:
        require(r.assembly_id in objects and ident(r.role) and ident(r.source_ref) and 1<=r.minimum_count<=64,'INVALID_REQUIREMENT')
        key=(r.assembly_id,r.role);require(key not in required,'DUPLICATE_REQUIREMENT')
        required[key]=r.minimum_count
    absent={}
    for a in request.absences:
        require(a.assembly_id in objects and ident(a.role) and ident(a.source_ref) and evidence(a.evidence),'INVALID_ABSENCE')
        key=(a.assembly_id,a.role);require(key not in absent,'DUPLICATE_ABSENCE')
        absent[key]=a
    funcs={}
    for f in request.functions:
        require(f.assembly_id in objects and ident(f.function_id) and ident(f.source_ref) and evidence(f.evidence) and 1<=len(f.required_roles)<=32 and len(set(f.required_roles))==len(f.required_roles) and all(ident(x) for x in f.required_roles),'INVALID_FUNCTION')
        key=(f.assembly_id,f.function_id);require(key not in funcs,'DUPLICATE_FUNCTION')
        funcs[key]=f
    keys=set(groups)|set(required)|set(absent)
    keys.update((f.assembly_id,role) for f in funcs.values() for role in f.required_roles)
    result=pb.AssemblyResearchResult(graph_id=request.graph_id,conversation_id=request.conversation_id,research_only=True,grants_authority=False)
    status={}
    for key in sorted(keys):
        members=groups[key]
        accepted=sorted({m.part_id for m in members if m.evidence!=pb.ASSEMBLY_HYPOTHETICAL and objects[m.part_id].evidence!=pb.ASSEMBLY_HYPOTHETICAL})
        limit=required.get(key,1)
        absence=absent.get(key)
        verified_absence=absence is not None and absence.evidence!=pb.ASSEMBLY_HYPOTHETICAL
        if accepted and verified_absence: s=pb.ASSEMBLY_CONTRADICTION
        elif verified_absence:s=pb.ASSEMBLY_EXPLICIT_ABSENCE
        elif len(accepted)>=limit:s=pb.ASSEMBLY_PRESENT_CLAIM
        else:s=pb.ASSEMBLY_NOT_ESTABLISHED
        finding=result.roles.add(assembly_id=key[0],role=key[1],status=s,claimed_count=len(accepted),required_count=limit,part_ids=accepted)
        if any(m.evidence==pb.ASSEMBLY_INFERRED for m in members):finding.warnings.append('INFERRED_MEMBERSHIP_UNCONFIRMED')
        if any(m.evidence==pb.ASSEMBLY_HYPOTHETICAL for m in members) or (absence and absence.evidence==pb.ASSEMBLY_HYPOTHETICAL):finding.warnings.append('HYPOTHETICAL_NOT_PROMOTED')
        if s==pb.ASSEMBLY_CONTRADICTION:finding.warnings.append('PRESENCE_AND_ABSENCE_CONFLICT')
        if s==pb.ASSEMBLY_NOT_ESTABLISHED:finding.warnings.append('MISSING_EVIDENCE_DOES_NOT_PROVE_ABSENCE')
        status[key]=s
    for key in sorted(funcs):
        f=funcs[key];ok=all(status[(f.assembly_id,role)]==pb.ASSEMBLY_PRESENT_CLAIM for role in f.required_roles)
        finding=result.functions.add(assembly_id=f.assembly_id,function_id=f.function_id,required_roles_claimed=ok)
        if not ok:finding.reasons.append('REQUIRED_ROLES_NOT_ESTABLISHED_OR_CONTRADICTED')
        if f.evidence==pb.ASSEMBLY_HYPOTHETICAL:finding.reasons.append('FUNCTION_HYPOTHETICAL')
        finding.reasons.append('ROLE_PRESENCE_DOES_NOT_PROVE_FUNCTIONAL_PERFORMANCE')
        finding.reasons.append('NO_REAL_WORLD_ACTION_AUTHORITY')
    result.warnings.extend(['CALLER_ASSERTED_PROVENANCE_NOT_AUTHENTICATED','SHARED_MEMBERSHIP_NOT_PHYSICAL_OWNERSHIP','NO_ABSENCE_INFERRED_FROM_MISSING_PART','NO_ACTION_AUTHORITY'])
    return result
