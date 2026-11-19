"""MEL-03B2 trusted-host reference admission for compute-only mathematical operations.

Not a Lu grant issuer, RPC server, or OS sandbox. Host callers must already be
trusted; model data is only a closed reviewed Protobuf request frame. Use one instance per
host session, retire it at session shutdown. Grants never enter model schemas.
The existing Runtime/Registry/worker remain the sole computation path.
"""
from dataclasses import dataclass
from enum import Enum
import hashlib
import secrets
from threading import RLock
from time import monotonic_ns

from cognitum.contracts import HostContext, Request
from cognitum.runtime import Runtime
from . import native as n

MAX_GRANTS = 64
MAX_REQUESTS = 256
MAX_INFLIGHT = 4
MAX_TTL_MS = 60000
MAX_WORK = (256 + 1)*32*8


class Effect(str, Enum):
    COMPUTE_ONLY = 'compute_only'


def _ids(*values):
    return all(type(v) is str and n.ID.fullmatch(v) for v in values)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _int(value, lo, hi):
    return type(value) is int and lo <= value <= hi


@dataclass(frozen=True, slots=True)
class Scope:
    session: str
    workspace: str
    subject: str
    turn: str

    def __post_init__(self):
        _require(_ids(self.session, self.workspace, self.subject, self.turn), 'invalid host scope')


@dataclass(frozen=True, slots=True)
class Limits:
    dimensions: int = 8
    terms: int = 32
    points: int = 16
    request_bytes: int = n.MAX_REQUEST
    result_bytes: int = n.MAX_RESULT
    timeout_ms: int = 3000
    calls: int = 1
    work: int = (32+1)*16*8

    def __post_init__(self):
        _require(all(_int(v, lo, hi) for v, lo, hi in (
            (self.dimensions,1,8), (self.terms,0,256), (self.points,1,32),
            (self.request_bytes,1,n.MAX_REQUEST), (self.result_bytes,1,n.MAX_RESULT),
            (self.timeout_ms,1,10000), (self.calls,1,16), (self.work,1,16*MAX_WORK))), 'invalid grant limits')


@dataclass(frozen=True, slots=True)
class Route:
    public_name: str
    operation: str
    descriptor_sha256: str
    effect: Effect
    input_type_url: str
    output_type_url: str
    operation_version: str


def routes(*, include_engines=False):
    _require(type(include_engines) is bool, 'explicit engine selection')
    vfa = tuple(Route(b['public_name'], b['operation'], h, Effect.COMPUTE_ONLY,
                       *b['native_proto_type_urls'], b['operation_schema_version']) for h,b in n.catalog())
    if not include_engines:return vfa
    from . import engines as e
    return vfa+tuple(Route('mel_'+b['operation'].replace('.','_'),b['operation'],h,Effect.COMPUTE_ONLY,
                           *b['native_proto_type_urls'],b['operation_schema_version']) for h,b in e.catalog())


@dataclass(frozen=True, slots=True)
class Receipt:
    scope: Scope
    request_id: str
    operation: str
    descriptor_sha256: str
    request_sha256: str
    status: str
    result_frame: bytes | None = None
    result_sha256: str | None = None


@dataclass(slots=True)
class _Grant:
    scope: Scope
    route: Route
    limits: object
    expires: int
    entry: object
    calls_left: int
    work_left: int
    revoked: bool = False
    model_codec: bool = False
    checkpoint: object = None


@dataclass(slots=True)
class _Call:
    grant: _Grant
    deadline: int
    cancelled: bool = False
    dispatched: bool = False


class Admission:
    """Trusted host-only interface; no ambient grant, no arbitrary plugin route.

    The grant table is bounded and never evicts replay tombstones. A trusted host
    creates a new session after retiring this one. Revocation/cancellation is
    linearized against result publication by _lock. Once dispatched, a trusted
    inert worker may finish or hit Runtime's timeout; its result is discarded if
    cancelled/revoked/expired. Registry lock pins the exact installed entry until
    dispatch returns; registry mutations can wait for bounded worker cleanup.
    No immediate worker interrupt or protected OS custody is implied.
    """
    def __init__(self, runtime, session, *, enable_engines=False, enable_model_codecs=False):
        _require(type(runtime) is Runtime and _ids(session), 'trusted runtime and session required')
        _require(type(enable_engines) is bool, 'explicit engine enable flag')
        _require(type(enable_model_codecs) is bool and (not enable_model_codecs or enable_engines), 'explicit model codec enable flag')
        self._enable_model_codecs = enable_model_codecs
        self._checkpoints = {}
        self._revoked_checkpoints = set()
        self._enable_engines = enable_engines
        self._runtime = runtime
        self._session = session
        self._lock = RLock()
        self._grants = {}
        self._seen = set()
        self._active = {}
        self._closed = False

    def _scope(self, scope):
        _require(type(scope) is Scope and scope.session == self._session, 'invalid host session')

    def _entry(self, route):
        # Caller holds registry lock. Check live nomination AND full descriptor.
        registry = self._runtime.registry
        if route.operation in n.OP:
            n.discover(registry, ((route.public_name, route.descriptor_sha256),))
            factory = n.NativeVFAPlugin
        else:
            from . import engines as e
            _require(self._enable_engines, 'engine admission disabled')
            e.discover(registry, ((route.operation,route.descriptor_sha256),))
            factory = e.EnginePlugin
        entry, op = registry.resolve(route.operation, allow_research=True)
        _require(entry.factory is factory and not op.effects and op.deterministic
                 and op.schema_version == route.operation_version, 'not reviewed compute-only route')
        return entry

    def issue(self, scope, route, limits=Limits(), *, ttl_ms=10000, model_codec=False, checkpoint_sha256=None):
        """Trusted authorization decision only; never called from model JSON."""
        self._scope(scope)
        _require(type(route) is Route and route in routes(include_engines=self._enable_engines) and route.effect is Effect.COMPUTE_ONLY
                 and _int(ttl_ms,1,MAX_TTL_MS), 'invalid compute grant')
        if route.operation in n.OP:
            expected = Limits
        else:
            from .engine_limits import limits_type
            expected = limits_type(route.operation)
        _require(type(limits) is expected, 'wrong operation resource profile')
        _require(type(model_codec) is bool and (not model_codec or (self._enable_model_codecs and route.operation not in n.OP)), 'model codec unavailable')
        _require((type(checkpoint_sha256) is str and model_codec and route.operation=='kan.evaluate') or (checkpoint_sha256 is None and not (model_codec and route.operation=='kan.evaluate')), 'checkpoint selection')
        with self._runtime.registry.lock:
            entry = self._entry(route)
            with self._lock:
                _require(not self._closed and len(self._grants)<MAX_GRANTS, 'grant capacity or session closed')
                approval=None
                if checkpoint_sha256 is not None:
                    from .model_engines import DIGEST
                    _require(DIGEST.fullmatch(checkpoint_sha256),'checkpoint pin')
                    key=(scope,checkpoint_sha256)
                    _require(key in self._checkpoints and key not in self._revoked_checkpoints,'checkpoint not approved for scope')
                    approval=self._checkpoints[key]
                token = secrets.token_bytes(32)
                while token in self._grants:
                    token = secrets.token_bytes(32)
                self._grants[token] = _Grant(scope,route,limits,monotonic_ns()+ttl_ms*1000000,
                                             entry,limits.calls,limits.work,model_codec=model_codec,checkpoint=approval)
                return token

    def approve_checkpoint(self, scope, wire, *, expected_sha256, review_id):
        """Trusted explicit approval of exact layer-only protobuf; no paths or pickle."""
        from . import model_engines as m
        self._scope(scope);_require(self._enable_model_codecs,'checkpoint custody disabled')
        _require(type(expected_sha256) is str and m.DIGEST.fullmatch(expected_sha256),'checkpoint pin')
        c=m.Checkpoint(wire);_require(c.identity==expected_sha256,'checkpoint pin mismatch')
        approval=m.Approval(c,review_id);key=(scope,c.identity)
        with self._lock:
            _require(not self._closed and len(self._checkpoints)<m.MAX_CHECKPOINTS and key not in self._checkpoints,'checkpoint capacity or duplicate approval')
            self._checkpoints[key]=approval
        return c.identity

    def revoke_checkpoint(self, scope, identity):
        self._scope(scope);_require(type(identity) is str,'checkpoint identity')
        key=(scope,identity)
        with self._lock:
            if key not in self._checkpoints or key in self._revoked_checkpoints:return False
            self._revoked_checkpoints.add(key);approval=self._checkpoints[key]
            for g in self._grants.values():
                if g.checkpoint is approval:g.revoked=True
            return True

    def discover_model(self, scope, token):
        """Scoped inert model descriptor; native Lu registration remains pending."""
        from . import model_engines as m
        self._scope(scope)
        with self._runtime.registry.lock:
            with self._lock:
                g=self._grant(scope,token)
                _require(self._live(g,scope) and g.model_codec and g.calls_left>0 and g.work_left>0,'model grant unavailable')
                _require(self._entry(g.route) is g.entry,'installed entry changed')
                return m.offer(g.route.operation,g.checkpoint)

    def execute_model(self, scope, token, request_id, public_name, codec_sha256, raw_arguments, *, timeout_ms):
        """Host supplies opaque grant, exact descriptor and IDs; model supplies only JSON args."""
        from . import model_engines as m
        self._scope(scope)
        with self._lock:
            g=self._grant(scope,token)
            _require(self._live(g,scope) and g.model_codec,'model grant unavailable')
            op=g.route.operation;approval=g.checkpoint
            _require(public_name==g.route.public_name and codec_sha256==m.descriptor(op)[0],'model route or codec mismatch')
        c=m.bind(op,approval,raw_arguments,request_id,scope.turn)
        r=self.execute(scope,token,request_id,c.wire,timeout_ms=timeout_ms)
        _require(r.scope==scope,'result scope mismatch')
        return m.feedback(c,approval,r)

    def _grant(self, scope, token):
        return self._grants.get(token) if type(token) is bytes and len(token)==32 else None

    def _live(self, g, scope):
        return (g is not None and g.scope == scope and not self._closed and not g.revoked
                and monotonic_ns() < g.expires)

    def discover(self, scope, token):
        """Only the one current scoped candidate schema; not actual Lu registration."""
        self._scope(scope)
        with self._runtime.registry.lock:
            with self._lock:
                g = self._grant(scope, token)
                _require(self._live(g,scope) and g.calls_left>0 and g.work_left>0, 'grant unavailable')
                _require(self._entry(g.route) is g.entry, 'installed entry changed')
                if g.route.operation not in n.OP:
                    # Inert typed host metadata only. C3 owns model schemas.
                    from . import engines as e
                    h,b=e.discover(self._runtime.registry, ((g.route.operation,g.route.descriptor_sha256),))[0]
                    return {'descriptor_sha256':h,'descriptor':b,'model_advertised':False}
                offer = n.discover(self._runtime.registry, ((g.route.public_name,g.route.descriptor_sha256),))[0]
                return offer['tool_schema']

    def revoke(self, scope, token):
        self._scope(scope)
        with self._lock:
            g=self._grant(scope,token)
            if g is None or g.scope!=scope or g.revoked:return False
            g.revoked=True
            return True

    def cancel(self, scope, request_id):
        self._scope(scope)
        _require(_ids(request_id), 'invalid request ID')
        with self._lock:
            call=self._active.get((scope,request_id))
            if call is None or call.cancelled:return False
            call.cancelled=True
            return True

    def close(self):
        """Host session shutdown: refuse admission and suppress all outstanding results."""
        with self._lock:
            self._closed=True
            for g in self._grants.values():g.revoked=True

    def _terminal(self, record):
        if record.cancelled:return 'cancelled'
        if self._closed or record.grant.revoked:return 'revoked'
        if monotonic_ns() >= record.deadline:return 'timed_out'
        return None

    def execute(self, scope, token, request_id, raw, *, timeout_ms):
        """Admit exact protobuf bytes from trusted host codec, not model authority.

        Reject wrong scope, route, type, descriptor, turn, request, budget and
        replay. Charge cumulative work and calls once reserved, even on failure.
        Only a validated successful frame can be returned, to this invocation's
        scope; no global result retrieval, no model-supplied response acceptance.
        """
        start=monotonic_ns()
        self._scope(scope)
        _require(_ids(request_id) and _int(timeout_ms,1,10000), 'invalid host call')
        with self._lock:
            g=self._grant(scope,token)
            # Non-owner cannot inspect the operation, grant, or its request history.
            if not self._live(g,scope):raise ValueError('grant unavailable')
            route=g.route;limits=g.limits
        if route.operation in n.OP:
            backend=n
        else:
            from . import engines as backend
        def receipt(status,frame=None):
            return Receipt(scope,request_id,route.operation,route.descriptor_sha256,
                           hashlib.sha256(raw).hexdigest() if type(raw) is bytes and len(raw)<=backend.MAX_REQUEST else '',
                           status,frame,hashlib.sha256(frame).hexdigest() if frame is not None else None)
        if type(raw) is not bytes or not 1<=len(raw)<=limits.request_bytes or timeout_ms>limits.timeout_ms:
            return receipt('resource_denied')
        try:
            if backend is n:
                c=n.decode_request(raw,route.operation)
                _require(c.request_id==request_id and c.correlation_id==scope.turn and c.descriptor_sha256==route.descriptor_sha256,'request ownership')
                f,p=n.pair(c.function,c.points);t,d=f.body.shape;count=p.body.shape[0]
                work=(t+1)*d*count if d<=limits.dimensions and t<=limits.terms and count<=limits.points else None
            else:
                from .engine_limits import account
                c=backend.Call(route.operation,raw);m=c.message
                _require(m.request_id==request_id and m.correlation_id==scope.turn and m.descriptor_sha256.hex()==route.descriptor_sha256,'request ownership')
                if g.model_codec:
                    from .model_engines import matches
                    _require(matches(c,g.checkpoint),'model subset or checkpoint mismatch')
                work=account(c,limits)
        except (ValueError,TypeError):return receipt('invalid_input')
        if work is None:return receipt('resource_denied')
        key=(scope,request_id)
        with self._lock:
            if not self._live(g,scope):return receipt('revoked' if g.revoked or self._closed else 'timed_out')
            if key in self._seen:return receipt('replay_denied')
            if g.calls_left<1 or g.work_left<work or len(self._seen)>=MAX_REQUESTS or len(self._active)>=MAX_INFLIGHT:
                return receipt('resource_denied')
            deadline=min(g.expires,start+timeout_ms*1000000)
            if monotonic_ns()>=deadline:return receipt('timed_out')
            record=_Call(g,deadline);self._seen.add(key);self._active[key]=record
            g.calls_left-=1;g.work_left-=work
        status='error';frame=None;locked=False
        registry=self._runtime.registry
        try:
            # Wait in short bounded increments so cancellation is observable before dispatch.
            while not locked:
                with self._lock:
                    status=self._terminal(record)
                if status:break
                remaining=(record.deadline-monotonic_ns())/1e9
                if remaining<=0:status='timed_out';break
                locked=registry.lock.acquire(timeout=min(.02,remaining))
            if locked:
                with self._lock:
                    status=self._terminal(record)
                    if status is None:
                        try:
                            if self._entry(route) is not g.entry:status='unavailable'
                        except ValueError:status='unavailable'
                    if status is None:
                        remaining=(record.deadline-monotonic_ns())//1000000
                        if remaining<1:status='timed_out'
                        else:record.dispatched=True
                if record.dispatched:
                    response=self._runtime.call(Request(request_id,scope.turn,route.operation,c.payload(),
                        workspace_id=scope.workspace,subject_id=scope.subject,operation_schema_version=route.operation_version,
                        timeout_ms=int(min(remaining,limits.timeout_ms))), HostContext(scope.workspace,scope.subject,allow_research=True))
                    # Runtime trusts only its installed factory; output is checked again against exact inputs.
                    if response.execution_status=='completed':
                        checked=backend.checked_result(c,response)
                        frame=n.decode_carrier(response.result['frame'],n.MAX_RESULT) if backend is n else checked
                        status='completed' if len(frame)<=limits.result_bytes else 'resource_denied'
                    else:
                        status=response.execution_status if response.execution_status in ('timed_out','unavailable','denied','invalid_input','error') else 'error'
        except Exception:
            status='error';frame=None
        finally:
            try:
                with self._lock:
                    # Completion vs cancellation/revocation has one linearization point.
                    status=self._terminal(record) or status or 'error'
                    self._active.pop(key,None)
                    result=receipt(status,frame if status=='completed' else None)
            finally:
                if locked:registry.lock.release()
        return result
