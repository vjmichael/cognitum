"""C15 T3 P2Z: standalone, fail-closed trusted-host integration readiness.

This is a host *contract*, not an implementation of a Lu trusted host. Host
keys, proof issuance and high-water anchors MUST stay outside the journal.
P2Z never deletes or rewrites P2Y records, nor authorizes its own repairs.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
import sys

from cognitum.proto import spatial_host_recovery_readiness_pb2 as zpb
from cognitum.proto import spatial_durable_incremental_volume_pb2 as ypb
from cognitum.proto import spatial_map_lifecycle_pb2 as wpb
from cognitum.spatial_durable_incremental_volume import (
    DurableRejected, P2YDurableSession, _ZERO, _hmac, _file_path,
    _list_records, _read_proto_exact, _safe_read, _valid_anchor, bits,
    genesis, MAX_RECORDS,
)


class HostReadinessRejected(DurableRejected):
    """Host binding, reconciliation, or platform readiness was rejected."""


def _binding(host):
    """Read a host-supplied binding and verify its exact wire representation."""
    raw = host.read_binding()
    if not isinstance(raw, zpb.P2ZHostBinding):
        raise HostReadinessRejected('INVALID_HOST_BINDING_TYPE')
    value = _read_proto_exact(zpb.P2ZHostBinding, bits(raw))
    if (value.schema_version != 1 or not value.research_only or
        value.grants_authority or not value.key_id or len(value.key_id) > 128 or
        not value.external_anchor):
        raise HostReadinessRejected('INVALID_HOST_BINDING')
    anchor = _read_proto_exact(ypb.P2YHostAnchor, value.external_anchor)
    if (not _valid_anchor(anchor) or
        (anchor.conversation_id, anchor.volume_id, anchor.authority_epoch) !=
        (value.conversation_id, value.volume_id, value.authority_epoch)):
        raise HostReadinessRejected('INVALID_OR_REVOKED_HOST_ANCHOR')
    return value, anchor


class _AnchorAdapter:
    """Translate the proposed host API to P2Y read/CAS without bypassing custody."""
    def __init__(self, host, initial_binding):
        self.host = host
        self.initial = initial_binding

    def _check(self):
        binding, anchor = _binding(self.host)
        if (binding.conversation_id != self.initial.conversation_id or
            binding.volume_id != self.initial.volume_id or
            binding.authority_epoch != self.initial.authority_epoch or
            binding.key_id != self.initial.key_id):
            raise HostReadinessRejected('KEY_OR_EPOCH_CHANGED_REOPEN_REQUIRED')
        return binding, anchor

    def read(self):
        return self._check()[1]

    def compare_and_swap(self, old, new):
        binding, current = self._check()
        if bits(old) != bits(current):
            return False
        # Only a real host is allowed to make this transaction durable.
        return bool(self.host.commit_update(binding, bits(old), bits(new)))


class _ReplayAnchor:
    """In-memory candidate anchor, used ONLY for independent read-only replay."""
    def __init__(self, anchor):
        self.anchor = anchor
    def read(self):
        c = ypb.P2YHostAnchor(); c.CopyFrom(self.anchor); return c
    def compare_and_swap(self, old, new):
        raise HostReadinessRejected('REPLAY_AUTHORITY_IS_READ_ONLY')


def _view(status, sequence, *, candidate=None, record_hash=b'', reason='', approval=False):
    return zpb.P2ZRecoveryPreview(schema_version=1, status=status,
        anchor_sequence=sequence,
        candidate_sequence=candidate.sequence if candidate is not None else 0,
        candidate_anchor=bits(candidate) if candidate is not None else b'',
        candidate_record_sha256=record_hash,
        reason=reason, requires_host_approval=approval,
        research_only=True, grants_authority=False)


class P2ZHostReadiness:
    """A tightly scoped host facade for a single conversation, volume and epoch.

    Required host methods (real implementations outside Cognitum):
      read_binding() -> P2ZHostBinding
      release_key(binding) -> 32+ byte host-controlled per-epoch secret
      commit_update(binding, expected_anchor_bytes, next_anchor_bytes) -> bool
      approve_reconciliation(binding, expected_anchor_bytes,
                             proposed_anchor_bytes, record_sha256,
                             opaque_proof) -> bool
    The host must enforce authorization, CAS, lease/revocation, one-time proof,
    key isolation and durable anchor storage; the adapter cannot guarantee them.
    """
    def __init__(self, journal_directory, *, host):
        self.root = Path(journal_directory)
        self.host = host
        self.binding, self.anchor = _binding(host)
        self.key = host.release_key(self.binding)
        if not isinstance(self.key, bytes) or len(self.key) < 32:
            raise HostReadinessRejected('MISSING_OR_WEAK_HOST_KEY')
        self.adapter = _AnchorAdapter(host, self.binding)
        if bits(self.adapter.read()) != bits(self.anchor):
            raise HostReadinessRejected('HOST_CHANGED_WHILE_OPENING')

    def _current(self):
        binding, anchor = self.adapter._check()
        if bits(binding) != bits(self.binding):
            # Anchor normally changes on every commit. Keep identity and epoch
            # pinned, but allow only explicit preview refresh to see new anchor.
            return binding, anchor
        return binding, anchor

    def open_session(self):
        # P2Y always verifies every committed record independently on restart.
        return P2YDurableSession(self.root, host_secret=self.key,
                                 authority=self.adapter)

    def inspect(self):
        """No repairs, no writes of record files; validates all candidate replay."""
        _, anchor = self._current()
        if not self.root.exists():
            return (_view('CLEAN', 0) if anchor.sequence == 0 else
                    _view('REJECTED', anchor.sequence, reason='MISSING_COMMITTED_JOURNAL'))
        try:
            actual = _list_records(self.root)
        except (OSError, DurableRejected) as ex:
            return _view('REJECTED', anchor.sequence, reason=str(ex))
        expected = list(range(1, anchor.sequence+1))
        if actual == expected:
            try:
                self.open_session()
            except (OSError, DurableRejected) as ex:
                return _view('REJECTED', anchor.sequence, reason=str(ex))
            return _view('CLEAN', anchor.sequence)
        if (anchor.sequence >= MAX_RECORDS or
            actual != list(range(1, anchor.sequence+2))):
            return _view('REJECTED', anchor.sequence,
                         reason='MISSING_MULTIPLE_OR_UNEXPECTED_RECORDS')
        try:
            raw = _safe_read(_file_path(self.root, anchor.sequence+1))
            rec = _read_proto_exact(ypb.P2YDurableRecord, raw)
            if (rec.schema_version != 1 or not rec.research_only or
                rec.grants_authority or rec.sequence != anchor.sequence+1 or
                rec.authority_epoch != anchor.authority_epoch or
                rec.conversation_id != anchor.conversation_id or
                rec.volume_id != anchor.volume_id or
                rec.preceding_hmac_sha256 != anchor.head_hmac_sha256 or
                not hmac.compare_digest(_hmac(self.key, rec), rec.record_hmac_sha256)):
                raise HostReadinessRejected('TAIL_CHAIN_OR_SCOPE_INVALID')
            req = _read_proto_exact(wpb.P2WUpdateRequest, rec.request)
            output = _read_proto_exact(wpb.P2WUpdateResult, rec.lifecycle)
            if (req.sequence != rec.sequence or not output.HasField('checkpoint') or
                req.source_request.dynamic_request.conversation_id != anchor.conversation_id or
                req.source_request.dynamic_request.volume_id != anchor.volume_id):
                raise HostReadinessRejected('TAIL_REQUEST_SCOPE_INVALID')
            candidate = ypb.P2YHostAnchor(); candidate.CopyFrom(anchor)
            candidate.sequence += 1
            candidate.head_hmac_sha256 = rec.record_hmac_sha256
            candidate.checkpoint_sha256 = output.checkpoint.checkpoint_sha256
            # The candidate is NOT authoritative: this checks existing bytes
            # against full independent replay before suggesting reconciliation.
            P2YDurableSession(self.root, host_secret=self.key,
                              authority=_ReplayAnchor(candidate))
            return _view('AUTHENTIC_UNANCHORED_TAIL', anchor.sequence,
                         candidate=candidate,
                         record_hash=hashlib.sha256(raw).digest(),
                         reason='HOST_APPROVAL_REQUIRED', approval=True)
        except (OSError, DurableRejected, ValueError) as ex:
            return _view('REJECTED', anchor.sequence, reason=str(ex))

    def reconcile(self, intent):
        """Complete exactly one fully replayed tail ONLY with external host approval.

        A host proof is opaque to Cognitum; the external host MUST verify it,
        enforce one-time use and atomically commit the exact proposed anchor.
        On commit failure records remain intact and recovery remains blocked.
        """
        if not isinstance(intent, zpb.P2ZReconcileIntent) or (
            intent.schema_version != 1 or not intent.research_only or
            intent.grants_authority or not intent.host_proof):
            raise HostReadinessRejected('MISSING_HOST_RECONCILIATION_APPROVAL')
        preview = self.inspect()
        binding, current = self._current()
        if (preview.status != 'AUTHENTIC_UNANCHORED_TAIL' or
            intent.key_id != binding.key_id or
            intent.expected_anchor != bits(current) or
            intent.candidate_anchor != preview.candidate_anchor or
            intent.candidate_record_sha256 != preview.candidate_record_sha256):
            raise HostReadinessRejected('RECONCILIATION_PREVIEW_STALE_OR_MISMATCHED')
        ok = self.host.approve_reconciliation(
            binding, intent.expected_anchor, intent.candidate_anchor,
            intent.candidate_record_sha256, intent.host_proof)
        if not ok:
            raise HostReadinessRejected('HOST_RECONCILIATION_DENIED')
        # Do not claim recovery until full verification against the real host.
        recovered = self.open_session()
        if bits(recovered.anchor) != intent.candidate_anchor:
            raise HostReadinessRejected('POST_COMMIT_ANCHOR_PARITY_FAILURE')
        return recovered


def platform_readiness():
    """Local capability inventory, not Windows fsync/ACL/crash certification."""
    return {
        'platform': sys.platform,
        'os_name': os.name,
        'p2y_exclusive_hardlink_supported': bool(hasattr(os, 'link')),
        'p2y_file_fsync_supported': bool(hasattr(os, 'fsync')),
        'windows_native_crash_powerloss_certified': False,
        'windows_acl_verified': False,
        'real_host_key_custody_verified': False,
        'real_host_cas_verified': False,
        'status': 'RESEARCH_ONLY_PLATFORM_VALIDATION_PENDING',
    }


def validate_epoch_transition(previous, successor, previous_directory, successor_directory):
    """Validate *host-issued* successor binding without migrating any records.

    This does not issue keys or authorize epoch rotation. An independent host
    must enroll the successor and retain the previous high-water anchor for
    audit/retention. Old journal records are never rewritten or discarded.
    """
    if not isinstance(previous, zpb.P2ZHostBinding) or not isinstance(successor, zpb.P2ZHostBinding):
        raise HostReadinessRejected('ROTATION_BINDING_MISSING')
    a = _read_proto_exact(ypb.P2YHostAnchor, previous.external_anchor)
    b = _read_proto_exact(ypb.P2YHostAnchor, successor.external_anchor)
    if (not _valid_anchor(a) or not _valid_anchor(b) or
        not previous.research_only or not successor.research_only or
        previous.grants_authority or successor.grants_authority or
        (a.conversation_id, a.volume_id) != (b.conversation_id, b.volume_id) or
        previous.conversation_id != successor.conversation_id or
        previous.volume_id != successor.volume_id or
        a.authority_epoch != previous.authority_epoch or
        b.authority_epoch != successor.authority_epoch or
        b.authority_epoch <= a.authority_epoch or b.sequence != 0 or
        previous.key_id == successor.key_id or not successor.key_id or
        Path(previous_directory).resolve() == Path(successor_directory).resolve() or
        Path(successor_directory).exists()):
        raise HostReadinessRejected('UNSAFE_EPOCH_ROTATION_ENROLLMENT')
    return True
