"""C15 T3 P2Y: bounded, externally anchored, fail-closed P2X restart journal.

The host MUST independently retain the current anchor and a secret key that is
not saved in this directory. No Lu host is integrated here. This research adapter
accepts an authority interface solely to test the host boundary. It does not
attest sensors, secure the filesystem from a privileged OS adversary, encrypt
camera data, or grant physical-world authority.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import stat
import threading

from cognitum.proto import spatial_durable_incremental_volume_pb2 as yp
from cognitum.proto import spatial_map_lifecycle_pb2 as wp
from cognitum.spatial_incremental_volume import P2XSession

MAX_RECORD_BYTES = 16_000_000
MAX_RECORDS = 256
_FILENAME = re.compile(r'^([0-9]{10})\.p2y$')
_ZERO = b'\x00' * 32

class DurableRejected(ValueError):
    """Durable record, source, authority or recovery invariant failed."""


def bits(msg):
    return msg.SerializeToString(deterministic=True)


def genesis(conversation_id: str, volume_id: str, epoch: int) -> yp.P2YHostAnchor:
    if (not conversation_id or not volume_id or not 0 < epoch < 2**64 or
            len(conversation_id) > 128 or len(volume_id) > 128):
        raise ValueError('INVALID_GENESIS_SCOPE')
    return yp.P2YHostAnchor(schema_version=1, conversation_id=conversation_id,
        volume_id=volume_id, authority_epoch=epoch, sequence=0,
        head_hmac_sha256=_ZERO, checkpoint_sha256=_ZERO, research_only=True)


def _valid_anchor(a):
    return (isinstance(a, yp.P2YHostAnchor) and a.schema_version == 1 and
            a.research_only and not a.grants_authority and not a.revoked and
            bool(a.conversation_id) and bool(a.volume_id) and
            0 < a.authority_epoch < 2**64 and a.sequence <= MAX_RECORDS and
            len(a.head_hmac_sha256) == 32 and len(a.checkpoint_sha256) == 32 and
            (a.sequence > 0 or (a.head_hmac_sha256 == _ZERO and
                                 a.checkpoint_sha256 == _ZERO)))


def _read_proto_exact(clazz, data):
    try:
        obj = clazz.FromString(data)
        known = clazz(); known.CopyFrom(obj); known.DiscardUnknownFields()
        if bits(obj) != data or bits(known) != data:
            raise DurableRejected('NON_CANONICAL_OR_UNKNOWN_PROTOBUF')
    except DurableRejected:
        raise
    except Exception as ex:
        raise DurableRejected('INVALID_JOURNAL_PROTOBUF') from ex
    return obj


def _file_path(root, sequence):
    return root / f'{sequence:010d}.p2y'


def _hmac(secret, record):
    copy = yp.P2YDurableRecord()
    copy.CopyFrom(record)
    copy.ClearField('record_hmac_sha256')
    return hmac.new(secret, b'Cognitum-P2Y-record-v1\0' + bits(copy), hashlib.sha256).digest()


def _safe_read(path):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, 'rb') as fh:
            metadata = os.fstat(fh.fileno())
            if not stat.S_ISREG(metadata.st_mode) or (os.name == 'posix' and (metadata.st_mode & 0o077)):
                raise DurableRejected('UNSAFE_JOURNAL_FILE')
            data = fh.read(MAX_RECORD_BYTES + 1)
    except OSError as ex:
        raise DurableRejected('MISSING_OR_UNSAFE_RECORD') from ex
    if not data or len(data) > MAX_RECORD_BYTES:
        raise DurableRejected('RECORD_SIZE_INVALID')
    return data


def _durable_write(path, data):
    if len(data) > MAX_RECORD_BYTES:
        raise DurableRejected('RECORD_SIZE_INVALID')
    tmp = path.with_name('.tmp-' + secrets.token_hex(12))
    flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL |
             getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
    try:
        with os.fdopen(os.open(tmp, flags, 0o600), 'wb') as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        # Hard-link is deliberately exclusive: never overwrite an existing record.
        os.link(tmp, path, follow_symlinks=False)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        tmp.unlink(missing_ok=True)


def _list_records(root):
    items = []
    for x in root.iterdir():
        if x.name.startswith('.tmp-'):
            raise DurableRejected('INCOMPLETE_RECORD_WRITE')
        if x.name == '.p2y.lock':
            continue
        m = _FILENAME.fullmatch(x.name)
        if not m or not x.is_file() or x.is_symlink():
            raise DurableRejected('UNEXPECTED_JOURNAL_ENTRY')
        items.append(int(m.group(1)))
    return sorted(items)


class P2YDurableSession:
    """Testable host-boundary implementation: authority.read + compare_and_swap.

    The host must atomically store each returned anchor outside the journal.
    After each disk fsync, compare_and_swap is the *commit point*. Failure
    freezes the session; recovery rejects an unanchored tail until a trusted
    administrator resolves it. This is intentional fail-closed behavior.
    """

    def __init__(self, directory, *, host_secret: bytes, authority):
        if not isinstance(host_secret, bytes) or len(host_secret) < 32:
            raise DurableRejected('MISSING_HOST_KEY')
        self._secret = host_secret
        self._authority = authority
        raw_root = Path(directory)
        if raw_root.is_symlink():
            raise DurableRejected('UNSAFE_JOURNAL_DIRECTORY')
        self._root = raw_root.resolve(strict=False)
        if self._root.is_symlink():
            raise DurableRejected('UNSAFE_JOURNAL_DIRECTORY')
        self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self._root.is_symlink() or not self._root.is_dir() or (
            os.name == 'posix' and (self._root.stat().st_mode & 0o077)):
            raise DurableRejected('UNSAFE_JOURNAL_DIRECTORY')
        self._lock = threading.RLock()
        self._poisoned = False
        self._session = P2XSession()
        self._anchor = None
        self._recover()

    @property
    def anchor(self):
        c = yp.P2YHostAnchor(); c.CopyFrom(self._anchor); return c

    def _read_host(self):
        anchor = self._authority.read()
        if not _valid_anchor(anchor):
            raise DurableRejected('MISSING_REVOKED_OR_INVALID_AUTHORITY')
        return anchor

    def _recover(self):
        host = self._read_host()
        expected = list(range(1, host.sequence + 1))
        if _list_records(self._root) != expected:
            raise DurableRejected('JOURNAL_ROLLBACK_GAP_OR_UNANCHORED_TAIL')
        prior = _ZERO
        last_checkpoint = _ZERO
        session = P2XSession()
        for seq in expected:
            record = _read_proto_exact(yp.P2YDurableRecord,
                                       _safe_read(_file_path(self._root, seq)))
            if (record.schema_version != 1 or not record.research_only or
                record.grants_authority or record.authority_epoch != host.authority_epoch or
                record.conversation_id != host.conversation_id or
                record.volume_id != host.volume_id or record.sequence != seq or
                record.preceding_hmac_sha256 != prior or
                len(record.record_hmac_sha256) != 32 or
                not hmac.compare_digest(_hmac(self._secret, record), record.record_hmac_sha256)):
                raise DurableRejected('JOURNAL_CHAIN_OR_AUTHENTICATION_FAILURE')
            request = _read_proto_exact(wp.P2WUpdateRequest, record.request)
            saved = _read_proto_exact(wp.P2WUpdateResult, record.lifecycle)
            if request.sequence != seq or not saved.HasField('checkpoint'):
                raise DurableRejected('JOURNAL_SEQUENCE_OR_CHECKPOINT_MISMATCH')
            try:
                recalculated = session.advance(request, validate_parity=True)
            except Exception as ex:
                raise DurableRejected('RESTART_FULL_REPLAY_FAILED') from ex
            if (bits(recalculated.lifecycle) != record.lifecycle or
                saved.checkpoint.checkpoint_sha256 != recalculated.lifecycle.checkpoint.checkpoint_sha256):
                raise DurableRejected('RESTART_REPLAY_PARITY_FAILURE')
            prior = record.record_hmac_sha256
            last_checkpoint = saved.checkpoint.checkpoint_sha256
        if host.head_hmac_sha256 != prior or host.checkpoint_sha256 != last_checkpoint:
            raise DurableRejected('HOST_ANCHOR_MISMATCH')
        self._anchor = host
        self._session = session  # cache rebuilt from independently verified records

    def advance(self, req):
        with self._lock:
            if self._poisoned:
                raise DurableRejected('UNCERTAIN_COMMIT_REQUIRES_RECOVERY')
            current = self._read_host()  # live revocation/epoch and stale writer guard
            if bits(current) != bits(self._anchor):
                raise DurableRejected('REVOKED_EPOCH_CHANGED_OR_STALE_WRITER')
            if self._anchor.sequence >= MAX_RECORDS:
                raise DurableRejected('JOURNAL_CAPACITY_REACHED_COMPACTION_REQUIRED')
            if req.sequence != self._anchor.sequence + 1:
                raise DurableRejected('DURABLE_SEQUENCE_MISMATCH')
            if (req.source_request.dynamic_request.conversation_id != self._anchor.conversation_id or
                req.source_request.dynamic_request.volume_id != self._anchor.volume_id):
                raise DurableRejected('DURABLE_CROSS_SCOPE')
            # Re-run independent P2W replay before persistence; no P2X cache shortcut.
            output = self._session.advance(req, validate_parity=True)
            record = yp.P2YDurableRecord(schema_version=1,
                conversation_id=self._anchor.conversation_id,
                volume_id=self._anchor.volume_id, authority_epoch=self._anchor.authority_epoch,
                sequence=req.sequence, request=bits(req), lifecycle=bits(output.lifecycle),
                preceding_hmac_sha256=self._anchor.head_hmac_sha256, research_only=True)
            record.record_hmac_sha256 = _hmac(self._secret, record)
            newer = yp.P2YHostAnchor(); newer.CopyFrom(self._anchor)
            newer.sequence = req.sequence
            newer.head_hmac_sha256 = record.record_hmac_sha256
            newer.checkpoint_sha256 = output.lifecycle.checkpoint.checkpoint_sha256
            self._poisoned = True  # do not advance again if fsync/CAS fails
            try:
                _durable_write(_file_path(self._root, req.sequence), bits(record))
                ok = self._authority.compare_and_swap(self._anchor, newer)
                if not ok:
                    raise DurableRejected('HOST_ANCHOR_COMMIT_REJECTED')
            except Exception as ex:
                raise DurableRejected('DURABLE_COMMIT_IN_DOUBT') from ex
            self._anchor = newer
            self._poisoned = False
            return output
