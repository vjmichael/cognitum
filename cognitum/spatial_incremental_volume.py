"""C15 T3 P2X: bounded session-local exact-input memoization of P2V replay.

P2X reuses P2T and P2S computations only when their *entire deterministic
Protobuf requests* match a previously locally computed request. A cached P2V
result is accepted only after exact comparison with the caller-supplied result.
The public P2W merge is unchanged and remains the source of the output bits.

The journal uses a secret generated inside the running process to authenticate
its own receipts. It cannot attest cameras, object identities, a host, persistent
storage, or any prior process: host authority remains out of scope.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import hmac
import secrets

from cognitum.proto import spatial_incremental_volume_pb2 as pb
from cognitum.proto import spatial_dynamic_scene_robustness_pb2 as vp
from cognitum.proto import spatial_dynamic_scene_mapping_pb2 as up
from cognitum.proto import spatial_object_aware_volume_pb2 as tp
from cognitum.proto import spatial_temporal_consistency_pb2 as sp
from cognitum.spatial_dynamic_scene_robustness import _analyze, RobustnessRejected
from cognitum.spatial_dynamic_scene_mapping import _map_scene
from cognitum.spatial_object_aware_volume import analyze as p2t_analyze
from cognitum.spatial_temporal_consistency import reconcile as p2s_reconcile
from cognitum.spatial_map_lifecycle import (_validate_request, _merge_preverified,
                                            LifecycleRejected, _check_checkpoint)


class IncrementalRejected(ValueError):
    """Input, continuity, provenance or cache integrity is insufficient."""


def _serialize(msg):
    return msg.SerializeToString(deterministic=True)


def _sha(data):
    return hashlib.sha256(data).digest()


class P2XSession:
    """Isolated and bounded in-memory acceleration for one volume/conversation.

    Never expose `_evaluate_p2v` or cached substage outputs as public trust
    boundaries. `advance` checks a caller's source result and previous P2W
    checkpoint, and has an optional expensive full-replay parity guard.
    """

    def __init__(self, *, max_cache_bytes=16_000_000, max_entries=128):
        if not (128_000 <= max_cache_bytes <= 64_000_000 and
                2 <= max_entries <= 1024):
            raise ValueError('INVALID_CACHE_BUDGET')
        self.max_cache_bytes = max_cache_bytes
        self.max_entries = max_entries
        self._entries = OrderedDict()  # stage+sha(request) -> (response bytes, integrity tag)
        self._bytes = 0
        self._key = secrets.token_bytes(32)
        self._scope = None
        self._sequence = 0
        self._checkpoint_sha = b''
        self._last_receipt_mac = b''
        self._stats = {}

    @property
    def cached_bytes(self):
        return self._bytes

    @property
    def cache_entries(self):
        return len(self._entries)

    def _auth(self, label, blob):
        return hmac.new(self._key, label + blob, hashlib.sha256).digest()

    def _memo(self, stage, source, output_class, compute):
        request_blob = _serialize(source)
        key = (stage, _sha(request_blob))
        # The request itself is compared by full SHA-256; a collision would
        # violate standard cryptographic assumptions, not the cache contract.
        if key in self._entries:
            data, tag = self._entries.pop(key)
            if not hmac.compare_digest(self._auth(stage.encode(), key[1] + data), tag):
                self._entries.clear()
                self._bytes = 0
                raise IncrementalRejected('CACHE_INTEGRITY_FAILURE')
            self._entries[key] = (data, tag)
            self._stats[stage][0] += 1
            return output_class.FromString(data)
        output = compute()
        encoded = _serialize(output)
        self._stats[stage][1] += 1
        if len(encoded) <= self.max_cache_bytes:
            while self._entries and (len(self._entries) >= self.max_entries or
                                     self._bytes + len(encoded) > self.max_cache_bytes):
                _, (data, _) = self._entries.popitem(last=False)
                self._bytes -= len(data)
            self._entries[key] = (encoded, self._auth(stage.encode(), key[1] + encoded))
            self._bytes += len(encoded)
        return output_class.FromString(encoded)

    def _temporal(self, source):
        return self._memo('p2s', source, sp.P2STemporalResult,
                          lambda: p2s_reconcile(source))

    def _window(self, source):
        return self._memo('p2t', source, tp.P2TObjectAwareResult,
                          lambda: p2t_analyze(source))

    def _scene(self, source):
        return _map_scene(source, _evaluate_window=self._window,
                          _reconcile_temporal=self._temporal)

    def _p2v(self, source):
        return self._memo('p2v', source, vp.P2VRobustnessResult,
                          lambda: _analyze(source, _map_scene_eval=self._scene,
                                           _reconcile_temporal=self._temporal))

    def verify_receipt(self, receipt):
        if (not isinstance(receipt, pb.P2XReceipt) or receipt.schema_version != 1 or
            not receipt.research_only or receipt.grants_authority or
            len(receipt.receipt_hmac_sha256) != 32):
            return False
        copy = pb.P2XReceipt()
        copy.CopyFrom(receipt)
        copy.ClearField('receipt_hmac_sha256')
        return hmac.compare_digest(receipt.receipt_hmac_sha256,
            self._auth(b'P2X-receipt-v1', _serialize(copy)))

    def advance(self, req, *, validate_parity=False):
        """Verify and merge one sequential input. Output lifecycle equals P2W.

        With validate_parity=True an independent full P2W replay is performed
        and exact bytes compared; use in QA, not speed measurements.
        """
        _validate_request(req)
        scope = (req.source_request.dynamic_request.conversation_id,
                 req.source_request.dynamic_request.volume_id)
        if self._scope is not None and self._scope != scope:
            raise IncrementalRejected('CROSS_SCOPE_SESSION')
        if req.sequence != self._sequence + 1:
            raise IncrementalRejected('SESSION_SEQUENCE_MISMATCH')
        if self._sequence and (not req.HasField('previous') or
                              req.previous.checkpoint_sha256 != self._checkpoint_sha):
            raise IncrementalRejected('SESSION_CHECKPOINT_CHAIN_MISMATCH')
        if not self._sequence and req.HasField('previous'):
            raise IncrementalRejected('SESSION_UNANCHORED_PREDECESSOR')
        if req.HasField('previous'):
            _check_checkpoint(req.previous)
        self._stats = {x: [0, 0] for x in ('p2s','p2t','p2v')}
        try:
            evaluated = self._p2v(req.source_request)
        except (RobustnessRejected, ValueError) as exc:
            if isinstance(exc, IncrementalRejected):
                raise
            raise IncrementalRejected('UPSTREAM_REPLAY_REJECTED:' + str(exc)) from exc
        if _serialize(evaluated) != _serialize(req.source_result):
            raise IncrementalRejected('UNVERIFIED_UPSTREAM_P2V_RESULT')
        try:
            lifecycle = _merge_preverified(req)
        except LifecycleRejected as exc:
            raise IncrementalRejected('INVALID_LIFECYCLE:' + str(exc)) from exc
        if validate_parity:
            from cognitum.spatial_map_lifecycle import advance as full_advance
            if _serialize(full_advance(req)) != _serialize(lifecycle):
                raise IncrementalRejected('FULL_REPLAY_PARITY_FAILURE')
        receipt = pb.P2XReceipt(schema_version=1,conversation_id=scope[0],volume_id=scope[1],
                sequence=req.sequence,request_sha256=_sha(_serialize(req)),
                p2v_result_sha256=_sha(_serialize(evaluated)),
                checkpoint_sha256=lifecycle.checkpoint.checkpoint_sha256,
                previous_receipt_hmac_sha256=self._last_receipt_mac,
                research_only=True)
        receipt.receipt_hmac_sha256 = self._auth(b'P2X-receipt-v1', _serialize(receipt))
        output = pb.P2XIncrementalResult(schema_version=1, lifecycle=lifecycle, receipt=receipt,
            reused_p2t_windows=self._stats['p2t'][0],
            recomputed_p2t_windows=self._stats['p2t'][1],
            reused_temporal_windows=self._stats['p2s'][0],
            recomputed_temporal_windows=self._stats['p2s'][1],
            reused_p2v_result=bool(self._stats['p2v'][0]),
            full_replay_parity_verified=bool(validate_parity),research_only=True)
        self._scope = scope
        self._sequence = req.sequence
        self._checkpoint_sha = lifecycle.checkpoint.checkpoint_sha256
        self._last_receipt_mac = receipt.receipt_hmac_sha256
        return output
