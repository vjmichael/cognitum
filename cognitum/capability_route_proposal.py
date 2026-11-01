"""Cognitum-only reviewed capability *suggestions*; never an execution authority.

A host could use this metadata as one input when selecting relevant model
schemas, but host-side registration, per-turn grant, sandbox, and execution
must be implemented separately and explicitly.  Neither this module nor any
model/DLC-supplied bytes can authorize or execute a tool. No Lu changes.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import re
from .proto import specialists_pb2 as mp, formal_backend_pb2 as fb, formal_advanced_pb2 as fa
from .math_catalog import catalog as math_catalog, decode_catalog, encode_catalog

_MAX_USER_TEXT = 2048
_ID = re.compile(r'[a-z][a-z0-9_.-]{0,127}\Z', re.ASCII)

@dataclass(frozen=True)
class RouteDescriptor:
    """Immutable, locally reviewed type and effect identity (not permission)."""
    operation: str
    rule_id: str
    input_type_url: str
    output_type_url: str
    schema_sha256: str
    semantic_kind: str
    effect: str = 'none'
    approved_for_execution: bool = False

    def __post_init__(self):
        if any(type(x) is not str or not _ID.fullmatch(x) for x in (self.operation, self.rule_id)):
            raise ValueError('invalid route ID')
        if self.effect != 'none' or self.approved_for_execution is not False:
            raise ValueError('cannot grant execution or effects in a route descriptor')
        if type(self.schema_sha256) is not str or not re.fullmatch('[0-9a-f]{64}',self.schema_sha256):
            raise ValueError('invalid schema digest')
        if self.semantic_kind not in ('exact_linear','exact_symbolic','precision_decimal','finite_constraint'):
            raise ValueError('unreviewed semantic kind')
        for url in (self.input_type_url,self.output_type_url):
            if type(url) is not str or not re.fullmatch(r'type\.googleapis\.com/[A-Za-z0-9_.]+',url):
                raise ValueError('invalid protobuf type URL')

@dataclass(frozen=True)
class ProposedRoute:
    """Model-independent relevance suggestion. This cannot be passed as a grant."""
    operation: str
    rule_id: str
    descriptor_digest: str
    status: str = 'discovery_only_no_execution_permission'

    def __post_init__(self):
        if self.status != 'discovery_only_no_execution_permission':
            raise ValueError('unprivileged route proposal cannot be promoted')


def _schema_hash(input_class, output_class):
    h=hashlib.sha256()
    for cls in (input_class,output_class):
        h.update(cls.DESCRIPTOR.full_name.encode()+b'\0')
        h.update(hashlib.sha256(cls.DESCRIPTOR.file.serialized_pb).digest())
    return h.hexdigest()


def trusted_catalog():
    """Developer-defined reviewed *metadata*, not installable DLC manifest."""
    # Catch unintended alterations to the intentionally inert C05 catalog.
    decode_catalog(encode_catalog())
    existing={m.operation:m for m in math_catalog().specialists}
    specs=(
        ('cognitum.math.linear','c05.determinant','exact_linear',mp.LinearRequest,mp.LinearResult),
        ('cognitum.math.symbolic','c05.expand','exact_symbolic',mp.SymbolicRequest,mp.SymbolicResult),
        ('cognitum.math.precision','c05.decimal','precision_decimal',mp.PrecisionRequest,mp.PrecisionResult),
        ('cognitum.formal.finite','c10.boolean','finite_constraint',fb.BackendRun,fa.FiniteCertificate),
    )
    entries=[]
    for operation,rule,kind,ic,oc in specs:
        input_url='type.googleapis.com/'+ic.DESCRIPTOR.full_name
        output_url='type.googleapis.com/'+oc.DESCRIPTOR.full_name
        if operation in existing:
            m=existing[operation]
            if m.input_type_url!=input_url or m.output_type_url!=output_url or m.registered or m.model_advertised:
                raise ValueError('C05 metadata diverged from compiled protobuf or attempted activation')
        entries.append(RouteDescriptor(operation,rule,input_url,output_url,_schema_hash(ic,oc),kind))
    return tuple(entries)


def descriptor_digest(descriptor):
    if type(descriptor) is not RouteDescriptor:
        raise TypeError('reviewed descriptor required')
    raw='\0'.join((descriptor.operation,descriptor.rule_id,descriptor.input_type_url,
                   descriptor.output_type_url,descriptor.schema_sha256,descriptor.semantic_kind,
                   descriptor.effect,str(descriptor.approved_for_execution))).encode()
    return hashlib.sha256(raw).hexdigest()


def _relevance(question):
    """Conservative, hard-coded initial intent cues; not natural-language authorization."""
    text=' '.join(question.lower().split())
    result=[]
    # Don't let metadata supplied by a model specify executable rules/regex.
    if re.search(r'\b(?:compute|calculate|find|what is)\b.*\bdeterminant\b',text):
        result.append('c05.determinant')
    if re.search(r'\bexpand\b.*\b(?:polynomial|\(x[+-])',text):
        result.append('c05.expand')
    if re.search(r'\bcalculate\b.*\bexactly as a decimal\b',text):
        result.append('c05.decimal')
    if re.search(r'\bboolean\b.*\b(?:satisfy|satisfying|satisfiable)\b',text):
        result.append('c10.boolean')
    return result


def propose_route(user_text: str, *, reviewed_catalog=None):
    """Propose one trusted, relevant schema; never execute, grant, or advertise.

    No model-controlled schema content, executable path, process name,
    permission effect, or route rules are accepted. Collision => no proposal.
    """
    if type(user_text) is not str or not 1<=len(user_text)<=_MAX_USER_TEXT:
        return None
    text=' '.join(user_text.lower().split())
    if any(re.search(x,text) for x in (r'\bwithout (?:any )?(?:tools?|specialists?)\b',
         r'\bdo not use (?:any )?(?:tools?|specialists?)\b',
         r'\bno (?:tools?|specialists?)\b',r'\bnever call (?:a )?tool\b')):
        return None
    catalog=trusted_catalog()
    # A third-party catalog can't alter the locally reviewed definitions.
    if reviewed_catalog is not None and (type(reviewed_catalog) is not tuple or reviewed_catalog!=catalog):
        raise ValueError('unreviewed route metadata cannot be admitted')
    found=_relevance(user_text)
    if len(found)!=1:return None
    matches=[d for d in catalog if d.rule_id==found[0]]
    if len(matches)!=1:return None
    d=matches[0]
    return ProposedRoute(d.operation,d.rule_id,descriptor_digest(d))


def catalog_snapshot():
    """Deterministic proposal payload: all routes remain disabled/not installable."""
    rows=[]
    for d in trusted_catalog():
        rows.append({'operation':d.operation,'rule':d.rule_id,'inputTypeUrl':d.input_type_url,
            'outputTypeUrl':d.output_type_url,'schemaSHA256':d.schema_sha256,
            'descriptorSHA256':descriptor_digest(d),'effect':'none',
            'assuranceKind':d.semantic_kind,'defaultEnabled':False,
            'registeredInLu':False,'modelAdvertised':False,'executionAuthorized':False})
    return {'schema':'cognitum.route-proposal.v1','status':'reviewed_metadata_only_no_host_permission',
            'routingRulesOwner':'Cognitum developer source only','installable':False,
            'capabilities':rows}
