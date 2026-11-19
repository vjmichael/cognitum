"""MEL-03A reviewed discovery/codec reference, not Lu registration or authority.

Only fixed developer-reviewed operations have schemas. A trusted caller may
request a projection against the live reference registry. Neither a descriptor,
selection, nor bound call confers a host grant or dispatches any operation.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re
from types import MappingProxyType

from cognitum.contracts import CONTRACT_VERSION, Response
from cognitum.registry import Registry
from .objects import MathObject, SCHEMA, KERNEL, PRODUCER, canonical, gaussian, points, pair, need
from .vfa import VFAPlugin, OPERATIONS, NAME, VERSION, request_payload, checked_response

VERSION_ID = 'cognitum.mel.descriptor.v1'
CODEC = 'cognitum.mel.model_json.v1'
MAX_ARGS_BYTES = 65536  # Lu's current JSON argument byte limit
MAX_MODEL_TERMS = 32
MAX_MODEL_POINTS = 16
MAX_DEPTH = 12
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z', re.ASCII)
TOKEN_PATTERN = r'^(?:[A-Za-z][A-Za-z0-9_]{0,23}|1)$'
HASH_PATTERN = r'^[0-9a-f]{64}$'
LIMITATIONS = ('binary64_numerical_not_certified', 'represented_function_only',
               'units_are_labels_not_converted', 'intent_not_verified')
PUBLIC = MappingProxyType({'mel_vfa_evaluate': 'vfa.evaluate', 'mel_vfa_gradient': 'vfa.gradient'})


def sha(value):
    return hashlib.sha256(canonical(value).encode('ascii')).hexdigest()


def obj(fields):
    return {'type': 'object', 'additionalProperties': False,
            'required': sorted(fields), 'properties': fields}


def arr(items, lo, hi):
    return {'type': 'array', 'items': items, 'minItems': lo, 'maxItems': hi}


def num(lo=-1e6, hi=1e6):
    return {'type': 'number', 'minimum': lo, 'maximum': hi}


def const(value):
    return {'const': value}


def token_schema():
    return {'type': 'string', 'minLength': 1, 'maxLength': 24, 'pattern': TOKEN_PATTERN}


def arguments_schema():
    """Closed model JSON shape; cross-field/ragged/domain rules enforced by codec."""
    return obj({'axes': arr(obj({'name': token_schema(), 'unit': token_schema()}), 1, 8),
                'domain': arr(obj({'lower': num(), 'upper': num()}), 1, 8),
                'terms': arr(obj({'center': arr(num(), 1, 8),
                                  'width': arr(num(1e-3, 1e3), 1, 8), 'weight': num()}), 0, MAX_MODEL_TERMS),
                'constant': num(), 'output_unit': token_schema(),
                'points': arr(arr(num(), 1, 8), 1, MAX_MODEL_POINTS)})


def result_schema(operation):
    grad = operation == 'vfa.gradient'
    digest = {'type': 'string', 'pattern': HASH_PATTERN, 'minLength': 64, 'maxLength': 64}
    name = next(k for k, v in PUBLIC.items() if v == operation)
    base = {'tool': const(name), 'descriptor_sha256': digest}
    result = obj({'object_id': digest, 'function_id': digest, 'points_id': digest,
                  'kind': const('gradient' if grad else 'values'),
                  'axes': arr(arr(token_schema(), 2, 2), 1, 8),
                  'shape': arr({'type': 'integer', 'minimum': 1, 'maximum': MAX_MODEL_POINTS}, 2 if grad else 1, 2 if grad else 1),
                  'domain': arr(obj({'lower': num(), 'upper': num()}), 1, 8),
                  'units': arr(arr(token_schema(), 2, 2), 1, 8 if grad else 1),
                  'values': arr(arr(num(-1e12, 1e12), 1, 8) if grad else num(-1e12, 1e12), 1, MAX_MODEL_POINTS),
                  'assurance': const('numerical'), 'error': const('not_certified'),
                  'limitations': const(list(LIMITATIONS)), 'producer': const(PRODUCER),
                  'kernel_git_blob': const(KERNEL)})
    return {'oneOf': [obj(dict(base, ok=const(True), result=result)),
                      obj(dict(base, ok=const(False), error=obj({'code': {'enum': sorted(FAILURES.values())},
                                                                 'retryable': const(False)})))]}


FAILURES = MappingProxyType({'unavailable': 'UNAVAILABLE', 'denied': 'DENIED', 'invalid_input': 'INVALID_INPUT',
            'timed_out': 'TIMED_OUT', 'error': 'EXECUTION_ERROR', 'validated': 'NOT_EXECUTED'})


@dataclass(frozen=True, slots=True)
class Descriptor:
    """Snapshot of versioned schema and implementation identities, not a grant."""
    wire: str

    @property
    def body(self):
        return json.loads(self.wire)

    @property
    def identity(self):
        return hashlib.sha256(self.wire.encode('ascii')).hexdigest()

    def tool(self):
        b = self.body
        return {'type': 'function', 'function': {'name': b['public_name'], 'description': b['description'],
                                                 'parameters': b['arguments_schema']}}


def catalog():
    """Only developer-defined descriptors. Rebuilt defensively, no shared mutable schemas."""
    manifest = VFAPlugin().manifest().describe()
    result = []
    for name, op in sorted(PUBLIC.items()):
        operation = next(x for x in manifest['operations'] if x['name'] == op)
        desc = ('Evaluate a supplied diagonal Gaussian mixture at explicit points.' if op == 'vfa.evaluate'
                else 'Compute partial derivatives of a supplied diagonal Gaussian mixture at explicit points, in axis order.')
        desc += (' Use f(x)=constant+sum(weight*exp(-0.5*sum(((x-center)/width)^2))). '
                 'Provide ordered axes with unit tokens (1=dimensionless), finite lower<upper per axis, '
                 'one center and positive width per axis for each term, and in-domain points. '
                 'No unit conversion, fitting, symbolic proof, or guarantee about a physical target. '
                 'Values are numerical for the submitted function only; preserve limitations.')
        a, r = arguments_schema(), result_schema(op)
        b = dict(schema=VERSION_ID, codec=CODEC, public_name=name, operation=op, description=desc,
                 contract_version=CONTRACT_VERSION, operation_schema_version=operation['schema_version'],
                 plugin_name=NAME, plugin_version=VERSION, track='research', effects=[],
                 assurance='numerical', object_schema=SCHEMA, kernel_git_blob=KERNEL,
                 object_codec_git_blob='6428963d7e6b963aa75f3a2d93aebadba2ea6ac6',
                 runtime_adapter_git_blob='1ea893e7aef6d4476aa18e9bfc41b9fd30bdbc09',
                 runtime_manifest_sha256=sha(manifest), operation_sha256=sha(operation),
                 arguments_schema=a, arguments_schema_sha256=sha(a), result_schema=r, result_schema_sha256=sha(r),
                 max_argument_bytes=MAX_ARGS_BYTES, max_terms=MAX_MODEL_TERMS, max_points=MAX_MODEL_POINTS,
                 execution_authorized=False, model_advertised=False, lu_registered=False,
                 native_proto_type_urls=None, status='reviewed_reference_only')
        result.append(Descriptor(canonical(b)))
    return tuple(result)


def selection_for(public_names):
    """Trusted reference helper; not derived from model output or a grant."""
    need(type(public_names) is tuple and len(public_names) <= len(PUBLIC) and all(type(n) is str and n in PUBLIC for n in public_names) and len(set(public_names)) == len(public_names), 'invalid selection')
    return tuple((d.body['public_name'], d.identity) for d in catalog() if d.body['public_name'] in public_names)


def selected(selection):
    need(type(selection) is tuple and len(selection) <= len(PUBLIC), 'selection must be explicit')
    known = {d.body['public_name']: d for d in catalog()}
    found = {}
    for pair_id in selection:
        need(type(pair_id) is tuple and len(pair_id) == 2 and all(type(x) is str for x in pair_id), 'selection entry')
        name, digest = pair_id
        need(name in known and name not in found and digest == known[name].identity, 'unknown, duplicate or stale descriptor')
        found[name] = known[name]
    return tuple(found[n] for n in sorted(found))


def discover(registry, selection):
    """Project explicit reviewed IDs against live, enabled nominated reference plugin.

    No default/all-discovery and no host/model advertising. Empty selection is
    empty. Any unavailable, stale, or mismatched selected entry refuses atomically.
    Registry is trusted local code. MEL-03B must enforce per-turn scope and recheck
    authorization at dispatch; this check is not a lease or a permission token.
    """
    need(type(registry) is Registry, 'trusted reference registry required')
    ds = selected(selection)
    for d in ds:
        b = d.body
        resolved = registry.resolve(b['operation'], allow_research=True)
        need(resolved is not None, 'reference operation unavailable')
        entry, op = resolved
        need(entry.factory is VFAPlugin and entry.manifest.track == 'research' and
             sha(entry.manifest.describe()) == b['runtime_manifest_sha256'] and
             sha(op.describe()) == b['operation_sha256'], 'runtime descriptor mismatch')
    return tuple({'descriptor_sha256': d.identity, 'descriptor': d.body, 'tool_schema': d.tool(),
                  'status': 'reference_candidate_not_advertised', 'execution_authorized': False} for d in ds)


def strict_json(raw):
    need(type(raw) is str and 1 <= len(raw) <= MAX_ARGS_BYTES and raw.isascii(), 'argument byte budget or encoding')
    # Reject excessive structural nesting before invoking the JSON parser. Ignore quoted braces.
    quoted = escaped = False
    depth = 0
    for c in raw:
        if quoted:
            if escaped: escaped = False
            elif c == '\\': escaped = True
            elif c == '"': quoted = False
        elif c == '"': quoted = True
        elif c in '[{':
            depth += 1
            need(depth <= MAX_DEPTH, 'argument depth')
        elif c in ']}':
            depth -= 1
            need(depth >= 0, 'argument structure')
    need(not quoted and depth == 0, 'argument structure')
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'duplicate JSON key')
            out[k] = v
        return out
    def integer(s):
        need(len(s) <= 12, 'integer token budget')
        return int(s)
    def decimal(s):
        need(len(s) <= 64, 'decimal token budget')
        v = float(s)
        need(math.isfinite(v), 'nonfinite decimal')
        return v
    def bad(_):
        raise ValueError('nonfinite JSON constant')
    value = json.loads(raw, object_pairs_hook=pairs, parse_int=integer, parse_float=decimal, parse_constant=bad)
    need(type(value) is dict, 'object arguments required')
    return value


def fields(value, keys):
    need(type(value) is dict and set(value) == set(keys), 'closed argument object required')


def sequence(value, lo, hi):
    need(type(value) is list and lo <= len(value) <= hi, 'argument array budget')
    return value


@dataclass(frozen=True, slots=True)
class BoundCall:
    """Immutable pure codec output. Explicit host dispatch is a separate action."""
    public_name: str
    descriptor_sha256: str
    request_id: str
    correlation_id: str
    function: MathObject
    coordinates: MathObject

    def __post_init__(self):
        ds = selected(((self.public_name, self.descriptor_sha256),))
        need(len(ds) == 1 and all(type(i) is str and ID.fullmatch(i) for i in (self.request_id,self.correlation_id)), 'call identity')
        _, f, _, _, p, _ = pair(self.function, self.coordinates)
        need(f['shape'][0] <= MAX_MODEL_TERMS and p['shape'][0] <= MAX_MODEL_POINTS, 'model subset budget')

    @property
    def operation(self):
        return PUBLIC[self.public_name]

    def payload(self):
        return request_payload(self.function, self.coordinates)


def bind_call(registry, selection, public_name, raw_arguments, *, request_id, correlation_id):
    """Strict untrusted JSON -> existing typed MEL objects. Never calls Runtime."""
    offers = discover(registry, selection)
    match = next((x for x in offers if x['descriptor']['public_name'] == public_name), None)
    need(type(public_name) is str and match is not None, 'not selected')
    a = strict_json(raw_arguments)
    fields(a, ('axes','domain','terms','constant','output_unit','points'))
    axes=[]; domain=[]; centers=[]; widths=[]; weights=[]
    for x in sequence(a['axes'], 1, 8):
        fields(x, ('name','unit')); axes.append((x['name'], x['unit']))
    for x in sequence(a['domain'], len(axes), len(axes)):
        fields(x, ('lower','upper')); domain.append((x['lower'],x['upper']))
    for t in sequence(a['terms'], 0, MAX_MODEL_TERMS):
        fields(t, ('center','width','weight'))
        centers.append(sequence(t['center'], len(axes), len(axes)))
        widths.append(sequence(t['width'], len(axes), len(axes))); weights.append(t['weight'])
    f = gaussian(centers,widths,weights,constant=a['constant'],axes=axes,domain=domain,output_unit=a['output_unit'])
    xs = sequence(a['points'], 1, MAX_MODEL_POINTS)
    p = points(f, [sequence(x,len(axes),len(axes)) for x in xs])
    return BoundCall(public_name, match['descriptor_sha256'], request_id, correlation_id, f, p)


def decode_result(call, response):
    """Trusted Runtime response -> bounded typed feedback; no value proof or grant."""
    need(type(call) is BoundCall and type(response) is Response and response.contract_version == CONTRACT_VERSION,
         'typed response required')
    need((response.request_id,response.correlation_id,response.operation) == (call.request_id,call.correlation_id,call.operation), 'unrelated response')
    out = {'tool': call.public_name, 'descriptor_sha256':call.descriptor_sha256}
    if response.execution_status != 'completed':
        need(response.execution_status in FAILURES and response.result is None, 'unexpected failure response')
        return dict(out, ok=False, error={'code': FAILURES[response.execution_status], 'retryable': False})
    value = checked_response(response,call.operation,call.function,call.coordinates,request_id=call.request_id,correlation_id=call.correlation_id)
    m=value.metadata; v=list(value.values)
    if m['kind']=='gradient':
        d=m['shape'][1]; v=[v[i:i+d] for i in range(0,len(v),d)]
    return dict(out, ok=True, result=dict(object_id=value.identity,function_id=call.function.identity,points_id=call.coordinates.identity,
                kind=m['kind'], axes=m['axes'], shape=m['shape'], domain=[{'lower':float.fromhex(a),'upper':float.fromhex(b)} for a,b in m['box']],
                units=m['units'],values=v,assurance=m['assurance'],error=m['error'],
                limitations=list(LIMITATIONS),producer=m['producer'],kernel_git_blob=m['kernel']))
