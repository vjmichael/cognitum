"""MEL-06B-A: inert host interoperability adapter; no Lu integration.

Only trusted host code may use this API. It does not register, advertise,
authorize, dispatch, authenticate transport, or publish. Native IPC uses the
existing MEL protobuf messages, not an adapter-specific wire protocol.
"""
from dataclasses import dataclass
from hashlib import sha256

from . import admission as a, native as n, engines as e, model_engines as m
from . import model_reference as r, intent_reference as ir, discovery as d
from cognitum.registry import Registry

PROFILE = 'cognitum.mel.lu_adapter.v1'
OPERATIONS = tuple(sorted((*n.OP, *e.OPERATIONS)))


def _hash(raw):
    return sha256(raw).hexdigest()


def _route(operation):
    n.need(operation in OPERATIONS, 'unsupported adapter operation')
    return next(x for x in a.routes(include_engines=True)
                if x.operation == operation)


def _metadata(operation):
    route = _route(operation)
    if operation in n.OP:
        codec, body = n.descriptor(route.public_name)
        backend = body
    else:
        codec, body = m.descriptor(operation)
        _, backend = e.descriptor(operation)
    return {
        'operation': operation,
        'native_tool_id': 'cognitum.' + operation,
        'public_name': route.public_name,
        'required_effect': route.effect.value,
        'input_type_url': route.input_type_url,
        'output_type_url': route.output_type_url,
        'descriptor_sha256': route.descriptor_sha256,
        'codec_sha256': codec,
        'protobuf_descriptor_sha256': backend['protobuf_descriptor_sha256'],
        'operation_version': route.operation_version,
        'checkpoint_required': operation == 'kan.evaluate',
        'tool_schema': {'type': 'function', 'function': {
            'name': route.public_name, 'description': body['description'],
            'parameters': body['arguments_schema']}},
    }


def proposal():
    """Trusted review metadata only, never installable or advertised."""
    return {'profile': PROFILE, 'installable': False, 'registered': False,
            'model_advertised': False, 'execution_authorized': False,
            'routes': [_metadata(op) for op in OPERATIONS]}


@dataclass(frozen=True, slots=True)
class Prepared:
    """Immutable candidate, not an authorization token or runnable task."""
    intent: ir.Intent
    route: a.Route
    codec_sha256: str
    call: object
    tolerance: float
    approval: m.Approval | None

    @property
    def wire(self):
        return self.call.wire() if self.route.operation in n.OP else self.call.wire

    @property
    def identity(self):
        return ir.digest({'profile': PROFILE, 'intent': self.intent.identity,
            'descriptor': self.route.descriptor_sha256,
            'codec': self.codec_sha256, 'request': _hash(self.wire),
            'tolerance': self.tolerance})


def prepare(registry, intent, allowed, route, codec_sha256, raw_model,
            *, request_id):
    """Check an independently approved typed intent and bind exact native bytes.

    The host supplies the existing registry, selected route, policy and ID.
    The model supplies only its closed tool/arguments object. Preparing bytes
    is not proof of authorization: Lu must admit the exact request itself.
    """
    n.need(type(registry) is Registry and type(intent) is ir.Intent
           and type(allowed) is r.Allowed and type(route) is a.Route,
           'trusted host inputs required')
    op = intent.operation
    n.need(route == _route(op) and op in allowed.operations,
           'operation or selected route mismatch')
    meta = _metadata(op)
    n.need(type(codec_sha256) is str and codec_sha256 == meta['codec_sha256'],
           'stale codec')
    n.need(type(request_id) is str and n.ID.fullmatch(request_id),
           'host request identity')
    n.need(intent.matches(raw_model), 'model intent mismatch')
    approval = allowed.approval if op == 'kan.evaluate' else None
    if op == 'kan.evaluate':
        n.need(type(approval) is m.Approval and
               approval.checkpoint.identity == intent.checkpoint,
               'checkpoint mismatch')

    def bind(args):
        if op in n.OP:
            return n.bind_model(registry,
                ((route.public_name, route.descriptor_sha256),),
                route.public_name, args, request_id=request_id,
                correlation_id=intent.scope.turn)
        e.discover(registry, ((op, route.descriptor_sha256),))
        return m.bind(op, approval, args, request_id, intent.scope.turn)

    # Compare actual canonical protobuf bytes as well as represented JSON.
    # This preserves distinctions such as signed zero and prevents rewriting.
    _, args = r.parse_request(raw_model)
    with registry.lock:
        expected = bind(intent.arguments)
        actual = bind(args)
    candidate = Prepared(intent, route, codec_sha256, actual,
                         allowed.tolerance, approval)
    baseline = Prepared(intent, route, codec_sha256, expected,
                        allowed.tolerance, approval)
    n.need(candidate.wire == baseline.wire, 'typed intent mismatch')
    if op in n.OP:
        rows, cols = actual.points.message().body.shape
        count = rows * (cols if op == 'vfa.gradient' else 1)
    elif op == 'kan.evaluate':
        count = actual.message.kan.rows * actual.message.kan.layers[-1].outputs
    else:
        count = 1
    n.need(intent.component < count, 'approved component absent')
    return candidate


def verify_host_retained_receipt(prepared, receipt):
    """Independently verify a host-retained receipt; not authenticate it.

    Lu must authenticate provenance and check current grant, revocation,
    cancellation, replay and durable custody *before* using this function.
    No model-origin receipt is acceptable. Hashes bind content, not authority.
    Returns an unpublishable *candidate* for the host's final decision.
    """
    n.need(type(prepared) is Prepared and type(receipt) is a.Receipt,
           'trusted prepared request and receipt required')
    op = prepared.route.operation
    n.need(prepared.route == _route(op) and
           prepared.codec_sha256 == _metadata(op)['codec_sha256'],
           'descriptor or codec drift')
    rid = (prepared.call.request_id if op in n.OP else
           prepared.call.message.request_id)
    n.need((receipt.scope, receipt.request_id, receipt.operation,
            receipt.descriptor_sha256, receipt.request_sha256) ==
           (prepared.intent.scope, rid, op, prepared.route.descriptor_sha256,
            _hash(prepared.wire)), 'receipt identity mismatch')
    if receipt.status != 'completed':
        n.need(receipt.result_frame is None and receipt.result_sha256 is None,
               'refused receipt must not carry result')
        return {'ok': False, 'error': 'host_not_completed',
                'result': None, 'publication_authorized': False}
    cols = (prepared.call.points.message().body.shape[1] if op == 'vfa.gradient'
            else prepared.call.message.kan.layers[-1].outputs if op == 'kan.evaluate'
            else 1 if op in n.OP else 0)
    feedback, audit = r.verified_feedback(prepared.intent.scope, prepared.call,
        receipt, (prepared.tolerance,) * cols, prepared.approval)
    if not feedback['ok']:
        return {'ok': False, 'error': 'verification_refused',
                'result': None, 'publication_authorized': False}
    answer, projection = ir._projection(prepared.intent, feedback)
    body = {'prepared_sha256': prepared.identity,
            'request_sha256': audit['request_sha256'],
            'result_sha256': audit['result_sha256'],
            'projection': projection, 'answer': answer}
    # Return a detached canonical copy. No host grants, raw frames or
    # authenticated publication decisions are exposed via model feedback.
    return {'ok': True, 'candidate': d.strict_json(r.canonical(body)),
            'candidate_sha256': ir.digest(body),
            'publication_authorized': False}
