"""CH34 research-only independently pinned anchor ledger for CH33 proof journals.

A caller MUST retain the returned tip SHA-256 outside the writable anchor and
journal stores. This implementation does not confer authentication on a writer
who can modify those external pins. Linux/local-filesystem protocol only.
No stored manifest is accepted as a replacement for mathematical MPFR replay.
"""
from __future__ import annotations
import errno, hashlib, json, os, re, uuid
from pathlib import Path

HEX = re.compile(r'^[0-9a-f]{64}$')
RECORD = re.compile(r'^([0-9]{8})_([0-9a-f]{64})\.json$')
GENESIS = '0' * 64
MAX_RECORD = 16384
ATTESTATION_KEYS = {'case_id', 'binding_sha256', 'original_head_sha256',
                    'checkpoint_sha256', 'archive_sha256', 'nodes',
                    'archive_epochs', 'replay_status', 'mpfr_replayed_frames'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def strict_json(raw):
    def pairs(kv):
        d = {}
        for k, v in kv:
            if k in d:
                raise ValueError('Duplicate manifest key')
            d[k] = v
        return d
    obj = json.loads(raw, object_pairs_hook=pairs,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite number')))
    if canonical(obj) + b'\n' != raw:
        raise ValueError('Noncanonical anchor record')
    return obj


def directory_sync(root):
    fd = os.open(root, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try: os.fsync(fd)
    finally: os.close(fd)


def new_temp(root, data):
    p = root / ('.anchor-' + uuid.uuid4().hex + '.pending')
    fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    return p


def checked_record(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECORD:
        raise ValueError('Invalid anchor file')
    raw = path.read_bytes()
    obj = strict_json(raw)
    if not isinstance(obj, dict) or set(obj) != {'body', 'sha256'} or not isinstance(obj['body'], dict):
        raise ValueError('Anchor envelope malformed')
    if obj['sha256'] != digest(obj['body']):
        raise ValueError('Anchor digest mismatch')
    return obj


class AnchorLedger:
    """Immutable records and atomic HEAD; external expected tip required for trust.

    Preconditions: caller exclusively owns this directory for mutation; the
    ledger serializes local competing writers with flock on Linux. HEAD is a
    storage pointer, *not* a cryptographically trusted source of truth.
    """
    def __init__(self, root, *, max_ledger_bytes=None):
        self.root = Path(root).resolve()
        self.records = self.root / 'revisions'
        if max_ledger_bytes is not None and (type(max_ledger_bytes) is not int or max_ledger_bytes < 8192):
            raise ValueError('Ledger quota must be at least 8192 bytes')
        self.max_ledger_bytes = max_ledger_bytes
        self.root.mkdir(parents=True, exist_ok=True)
        self.records.mkdir(exist_ok=True)
        if self.records.is_symlink(): raise ValueError('Symlinked revision directory forbidden')

    def _files(self):
        for folder, allowed in ((self.root, {'.writer.lock', 'HEAD', 'revisions'}), (self.records, set())):
            for p in folder.iterdir():
                if p.is_symlink(): raise ValueError('Anchor symlink forbidden')
                if folder == self.root and p.name in allowed: continue
                if folder == self.records and RECORD.fullmatch(p.name): continue
                if re.fullmatch(r'\.anchor-[0-9a-f]{32}\.pending', p.name): continue
                raise ValueError('Unknown anchor path ' + p.name)

    def _pending(self):
        return [p for d in (self.root, self.records) for p in d.glob('.anchor-*.pending')]

    def read(self, *, expected_tip_sha256):
        if not isinstance(expected_tip_sha256, str) or not HEX.fullmatch(expected_tip_sha256):
            raise ValueError('Caller must supply an externally retained anchor tip')
        self._files()
        hp = self.root / 'HEAD'
        if not hp.is_file() or hp.is_symlink():
            if expected_tip_sha256 == GENESIS and not hp.exists(): return None
            raise ValueError('Missing durable HEAD; possible rollback')
        head = checked_record(hp)
        if head['sha256'] != expected_tip_sha256:
            raise ValueError('Stored HEAD differs from trusted external tip')
        cur = head
        seen = set()
        while True:
            b = cur['body']; sha = cur['sha256']
            required = {'version', 'generation', 'parent_sha256', 'case_id', 'binding_sha256',
                        'original_head_sha256', 'checkpoint_sha256', 'archive_sha256',
                        'nodes', 'archive_epochs', 'replay_status', 'mpfr_replayed_frames'}
            if set(b) != required or b['version'] != 1 or type(b['generation']) is not int or b['generation'] < 0:
                raise ValueError('Wrong anchor schema')
            if (type(b['nodes']) is not int or b['nodes'] < 1 or
                type(b['archive_epochs']) is not int or b['archive_epochs'] < 1 or
                type(b['mpfr_replayed_frames']) is not int or b['mpfr_replayed_frames'] < 1 or
                b['replay_status'] != 'REPLAYED_BUT_UNRESOLVED' or
                not isinstance(b['case_id'], str) or not b['case_id']):
                raise ValueError('Invalid attestation values')
            for name in ('parent_sha256', 'binding_sha256', 'original_head_sha256',
                         'checkpoint_sha256', 'archive_sha256'):
                if not isinstance(b[name], str) or not HEX.fullmatch(b[name]):
                    raise ValueError('Invalid anchor hash')
            path = self.records / f"{b['generation']:08d}_{sha}.json"
            if path in seen: raise ValueError('Circular anchor history')
            seen.add(path)
            if not path.is_file() or checked_record(path) != cur:
                raise ValueError('Missing or altered immutable anchor revision')
            if b['generation'] == 0:
                if b['parent_sha256'] != GENESIS:
                    raise ValueError('Broken anchor genesis')
                break
            parent_files = list(self.records.glob(f"{b['generation']-1:08d}_{b['parent_sha256']}.json"))
            if len(parent_files) != 1:
                raise ValueError('Missing anchor predecessor')
            cur = checked_record(parent_files[0])
            if cur['body']['generation'] != b['generation'] - 1:
                raise ValueError('Anchor generations not monotonic')
            if (cur['body']['case_id'], cur['body']['binding_sha256']) != (b['case_id'], b['binding_sha256']):
                raise ValueError('Anchor identity changed')
            if b['nodes'] < cur['body']['nodes'] or b['archive_epochs'] < cur['body']['archive_epochs']:
                raise ValueError('Anchor proof regression')
        return head

    def _size(self):
        return sum(p.stat().st_size for folder in (self.root, self.records) for p in folder.iterdir() if p.is_file())

    def publish(self, attestation, *, expected_tip_sha256, expected_source_head=None, fail_at=None):
        """Write immutable revision before HEAD; no automatic orphan adoption.

        fail_at is a deterministic fault-injection seam, not a power-loss test.
        Every 'ENOSPC' raises OSError; HEAD before publication remains valid.
        """
        import fcntl
        fd = os.open(self.root / '.writer.lock', os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            parent = self.read(expected_tip_sha256=expected_tip_sha256)
            if self._pending(): raise ValueError('Explicitly discard interrupted temporary writes first')
            reachable = set()
            cur = parent
            while cur is not None:
                b = cur['body']
                reachable.add(f"{b['generation']:08d}_{cur['sha256']}.json")
                if b['generation'] == 0: break
                cur = checked_record(self.records / f"{b['generation']-1:08d}_{b['parent_sha256']}.json")
            if any(RECORD.fullmatch(p.name) and p.name not in reachable for p in self.records.iterdir()):
                raise ValueError('Uncommitted orphan anchor revision requires explicit cleanup')
            if not isinstance(attestation, dict): raise ValueError('Invalid attestation')
            att = dict(attestation)
            if set(att) != ATTESTATION_KEYS:
                raise ValueError('Wrong attestation schema or attempted override of ledger fields')
            for k in ('binding_sha256','original_head_sha256','checkpoint_sha256','archive_sha256'):
                if not isinstance(att[k], str) or not HEX.fullmatch(att[k]):
                    raise ValueError('Invalid attestation digest')
            for k in ('nodes','archive_epochs','mpfr_replayed_frames'):
                if type(att[k]) is not int or att[k] <= 0:
                    raise ValueError('Invalid proof counters')
            if att['replay_status'] != 'REPLAYED_BUT_UNRESOLVED' or not isinstance(att['case_id'],str) or not att['case_id']:
                raise ValueError('Invalid proof disposition or case identity')
            if parent is None:
                if expected_source_head is None or att.get('original_head_sha256') != expected_source_head:
                    raise ValueError('Genesis requires independently pinned original source head')
            else:
                if (att.get('case_id'), att.get('binding_sha256')) != (parent['body']['case_id'], parent['body']['binding_sha256']):
                    raise ValueError('Cannot change anchored proof identity')
                if att['nodes'] < parent['body']['nodes'] or att['archive_epochs'] < parent['body']['archive_epochs']:
                    raise ValueError('Cannot regress anchored proof')
                if att['checkpoint_sha256'] == parent['body']['checkpoint_sha256']:
                    raise ValueError('Cannot claim a new anchor for unchanged checkpoint')
            body = {'version': 1, 'generation': 0 if parent is None else parent['body']['generation'] + 1,
                    'parent_sha256': GENESIS if parent is None else parent['sha256'], **att}
            entry = {'body': body, 'sha256': digest(body)}
            raw = canonical(entry) + b'\n'
            if len(raw) > MAX_RECORD: raise ValueError('Oversized anchor record')
            if self.max_ledger_bytes is not None and self._size() + 3 * len(raw) > self.max_ledger_bytes:
                raise OSError(errno.ENOSPC, 'Anchor storage quota exhausted before publication')
            target = self.records / f"{body['generation']:08d}_{entry['sha256']}.json"
            if target.exists(): raise ValueError('Anchor revision collision or uncommitted orphan')
            tmp = new_temp(self.records, raw)
            if fail_at == 'revision_temp': raise OSError(errno.ENOSPC, 'Injected revision temp failure')
            os.link(tmp, target)
            tmp.unlink()
            directory_sync(self.records)
            if fail_at == 'before_head': raise OSError(errno.ENOSPC, 'Injected failure before HEAD publication')
            hp = new_temp(self.root, raw)
            if fail_at == 'head_temp': raise OSError(errno.ENOSPC, 'Injected failure during HEAD temp write')
            os.replace(hp, self.root / 'HEAD')
            if fail_at == 'after_head_rename': raise OSError(errno.ENOSPC, 'Injected interruption after HEAD rename')
            directory_sync(self.root)
            return entry['sha256']
        finally:
            try: fcntl.flock(fd, fcntl.LOCK_UN)
            finally: os.close(fd)

    def discard_pending(self, *, expected_tip_sha256):
        import fcntl
        fd = os.open(self.root / '.writer.lock', os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            head = self.read(expected_tip_sha256=expected_tip_sha256)
            referenced = set(); cur = head
            while cur is not None:
                referenced.add(f"{cur['body']['generation']:08d}_{cur['sha256']}.json")
                b = cur['body']
                if b['generation'] == 0: break
                cur = checked_record(self.records / f"{b['generation']-1:08d}_{b['parent_sha256']}.json")
            orphans = [p for p in self.records.iterdir() if RECORD.fullmatch(p.name) and p.name not in referenced]
            pending = self._pending()
            for p in orphans + pending:
                if p.is_symlink(): raise ValueError('Symlinked orphan forbidden')
                p.unlink()
            directory_sync(self.records); directory_sync(self.root)
            return {'orphan_revisions_discarded': len(orphans), 'pending_files_discarded': len(pending)}
        finally:
            try: fcntl.flock(fd, fcntl.LOCK_UN)
            finally: os.close(fd)


def attestation_from_verified_ch33(journal, *, trusted_prior=None):
    """Call ONLY on an open CH33 journal with intact original CH23 inputs.

    This function *must* run expensive MPFR archived-history replay again.
    A journal receipt, checkpoint hash or saved cache is insufficient.
    """
    if not journal.full_mathematical_replay or journal._checkpoint is None:
        raise ValueError('Cold, mathematically verified CH33 recovery required')
    if journal._covered or journal._pending:
        raise ValueError('Unfinished CH33 journal cleanup: refuse anchoring')
    cp = journal._checkpoint['body']
    if trusted_prior is not None:
        prior = trusted_prior['body']
        if cp['prior_checkpoint_sha256'] != prior['checkpoint_sha256'] or cp['prior_head_sha256'] != prior['original_head_sha256']:
            raise ValueError('New CH33 checkpoint must extend last anchored checkpoint directly')
    history = journal.verify_archived_history()
    if history['final_original_head_sha256'] != cp['head_sha256'] or not history['archived_history_reverified_with_MPFR']:
        raise ValueError('Independent historical proof replay incomplete')
    return {'case_id': journal.case_id, 'binding_sha256': journal._bound(),
            'original_head_sha256': cp['head_sha256'],
            'checkpoint_sha256': journal._checkpoint['sha256'],
            'archive_sha256': cp['archive_sha256'],
            'nodes': cp['stage_nodes'], 'archive_epochs': history['archives'],
            'replay_status': 'REPLAYED_BUT_UNRESOLVED',
            'mpfr_replayed_frames': history['replayed_frames']}


def publish_verified_ch33(ledger, journal, *, expected_tip_sha256, expected_source_head=None,
                          expected_checkpoint_sha256=None):
    """Full CH33 MPFR replay before a new external anchor is committed.

    Ledger and externally retained tip must be owned by a distinct trust domain.
    Keep the returned SHA outside BOTH directories before authorizing writes.
    """
    anchor = ledger.root
    for mutable_dir in (journal.path.resolve(), journal.archive_dir.resolve()):
        if anchor == mutable_dir or anchor in mutable_dir.parents or mutable_dir in anchor.parents:
            raise ValueError('Independent anchor cannot share journal/archive subtree')
    prior = ledger.read(expected_tip_sha256=expected_tip_sha256)
    att = attestation_from_verified_ch33(journal, trusted_prior=prior)
    if prior is None:
        if expected_checkpoint_sha256 is None or expected_checkpoint_sha256 != att['checkpoint_sha256']:
            raise ValueError('Genesis requires independently pinned CH33 checkpoint hash')
    return ledger.publish(att, expected_tip_sha256=expected_tip_sha256,
                          expected_source_head=expected_source_head)


def reconcile_after_head_interruption(ledger, journal, *, trusted_prior_tip_sha256):
    """Explicit roll-forward check after HEAD rename; never repin automatically.

    The caller decides whether to retain the proposed SHA in an independent,
    durable external trust store. A raw HEAD hash by itself proves nothing.
    """
    hp = ledger.root / 'HEAD'
    candidate = checked_record(hp)
    candidate_sha = candidate['sha256']
    if candidate_sha == trusted_prior_tip_sha256:
        return {'status': 'PREVIOUS_ANCHOR_INTACT', 'tip_sha256': candidate_sha}
    if candidate['body']['parent_sha256'] != trusted_prior_tip_sha256:
        raise ValueError('HEAD is not a one-generation successor of trusted prior')
    verified = ledger.read(expected_tip_sha256=candidate_sha)
    b = verified['body']
    parent_path = ledger.records / f"{b['generation']-1:08d}_{trusted_prior_tip_sha256}.json"
    prior = checked_record(parent_path)
    if prior['sha256'] != trusted_prior_tip_sha256:
        raise ValueError('Untrusted prior anchor')
    actual = attestation_from_verified_ch33(journal, trusted_prior=prior)
    if {k: b[k] for k in ATTESTATION_KEYS} != actual:
        raise ValueError('Recovered anchor disagrees with fresh mathematical replay')
    return {'status': 'REQUIRES_EXTERNAL_REPIN', 'tip_sha256': candidate_sha,
            'original_head_sha256': actual['original_head_sha256'],
            'checkpoint_sha256': actual['checkpoint_sha256']}