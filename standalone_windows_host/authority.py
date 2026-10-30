"""P2Z *standalone validation host*, not a Lu trusted host or antirollback authority.

Windows: user-scoped DPAPI encrypted state and restricted ACLs; atomic write-
through state replacement and process lock. Linux: explicit INSECURE test backend.
A same-user filesystem adversary can roll back state + journal together. No
production authority/consent, TPM monotonic counter, or hardware-backed keys.
"""
from __future__ import annotations
from contextlib import contextmanager
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sys
from .platform_io import atomic_bytes, reject_reparse, dpapi_protect, dpapi_unprotect, windows_restrict_acl

from cognitum.proto import spatial_durable_incremental_volume_pb2 as ypb
from cognitum.proto import spatial_host_recovery_readiness_pb2 as zpb
from cognitum.spatial_durable_incremental_volume import genesis, bits
from cognitum.spatial_host_recovery_readiness import validate_epoch_transition

class AuthorityError(RuntimeError):pass

@contextmanager
def _lockfile(path):
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_BINARY if hasattr(os,'O_BINARY') else os.O_RDWR|os.O_CREAT,0o600)
    try:
        if os.name=='nt':
            import msvcrt
            if os.fstat(fd).st_size==0:os.write(fd,b'1');os.fsync(fd)
            os.lseek(fd,0,0)
            msvcrt.locking(fd,msvcrt.LK_LOCK,1)
        else:
            import fcntl
            fcntl.flock(fd,fcntl.LOCK_EX)
        yield
    finally:
        if os.name=='nt':
            os.lseek(fd,0,0);msvcrt.locking(fd,msvcrt.LK_UNLCK,1)
        else:fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)

class StandaloneAuthority:
    """Persistent local test host with epoch isolation and explicit reconciliation.

    Its protections harden test artifacts on Windows but DO NOT turn it into an
    independent host/rollback-resistant authority. Do not call from Lu.
    """
    def __init__(self,root,*,insecure_test_backend=False,crash_at=None):
        if os.name!='nt' and not insecure_test_backend:
            raise AuthorityError('WINDOWS_HOST_REQUIRES_WINDOWS; explicit test mode only elsewhere')
        if os.name=='nt' and insecure_test_backend:
            raise AuthorityError('WINDOWS_MUST_USE_DPAPI')
        self.root=Path(os.path.abspath(root))
        reject_reparse(self.root)
        self.root.mkdir(parents=True,exist_ok=True)
        if os.name=='nt':windows_restrict_acl(self.root)
        self.state=self.root/'protected-state.bin'
        self.lock=self.root/'authority.lock'
        self.insecure=os.name!='nt'
        self.crash_at=crash_at

    def _unseal(self,raw):
        if self.insecure:
            if not raw.startswith(b'INSECURE-TEST-ONLY\n'):raise AuthorityError('BAD_TEST_STATE')
            return raw[len(b'INSECURE-TEST-ONLY\n'):]
        if not raw.startswith(b'DPAPI-CURRENT-USER\n'):raise AuthorityError('STATE_NOT_DPAPI_PROTECTED')
        return dpapi_unprotect(raw[len(b'DPAPI-CURRENT-USER\n'):])

    def _seal(self,raw):
        if self.insecure:return b'INSECURE-TEST-ONLY\n'+raw
        return b'DPAPI-CURRENT-USER\n'+dpapi_protect(raw)

    def _load(self):
        reject_reparse(self.state)
        if not self.state.is_file():raise AuthorityError('AUTHORITY_NOT_ENROLLED')
        if self.state.stat().st_size > 2_000_000:raise AuthorityError('OVERSIZED_AUTHORITY_STATE')
        try:
            data=json.loads(self._unseal(self.state.read_bytes()))
        except Exception as ex:raise AuthorityError('AUTHORITY_STATE_INTEGRITY_FAILURE') from ex
        if data.get('schema')!=1 or data.get('backend')!=('test' if self.insecure else 'windows-dpapi'):
            raise AuthorityError('AUTHORITY_SCHEMA_OR_BACKEND_MISMATCH')
        return data

    def _save(self,data):
        raw=json.dumps(data,sort_keys=True,separators=(',',':')).encode('utf8')
        atomic_bytes(self.state,self._seal(raw))
        if os.name=='nt':windows_restrict_acl(self.state)

    def enroll(self,conversation_id,volume_id,*,epoch=1,journal_directory):
        with _lockfile(self.lock):
            if self.state.exists():raise AuthorityError('ALREADY_ENROLLED')
            journal=str(Path(os.path.abspath(journal_directory)))
            if Path(journal).exists():raise AuthorityError('NEW_JOURNAL_MUST_BE_ABSENT')
            if Path(journal)==self.root or self.root in Path(journal).parents:
                raise AuthorityError('AUTHORITY_AND_JOURNAL_MUST_BE_SEPARATE')
            a=genesis(conversation_id,volume_id,epoch)
            data={'schema':1,'backend':'test' if self.insecure else 'windows-dpapi',
                'conversation_id':conversation_id,'volume_id':volume_id,'epoch':epoch,
                'key_id':'epoch-'+str(epoch)+'-'+secrets.token_hex(8),
                'secret':base64.b64encode(secrets.token_bytes(48)).decode(),
                'anchor':bits(a).hex(),'journal':journal,'revoked':False,
                'history':[],'pending_approval':None}
            self._save(data)
            return self.read_binding()

    def _check_binding(self,s,binding):
        if s['revoked']:raise AuthorityError('EPOCH_REVOKED')
        if (binding.conversation_id!=s['conversation_id'] or
            binding.volume_id!=s['volume_id'] or binding.authority_epoch!=s['epoch'] or
            binding.key_id!=s['key_id']):
            raise AuthorityError('STALE_OR_CROSS_SCOPE_BINDING')

    @staticmethod
    def _binding_from(s):
        return zpb.P2ZHostBinding(schema_version=1,conversation_id=s['conversation_id'],
            volume_id=s['volume_id'],authority_epoch=s['epoch'],
            key_id=s['key_id'],external_anchor=bytes.fromhex(s['anchor']),research_only=True)

    def read_binding(self):
        s=self._load()
        if s['revoked']:raise AuthorityError('REVOKED_AUTHORITY_EPOCH')
        return self._binding_from(s)

    def release_key(self,binding):
        s=self._load();self._check_binding(s,binding)
        return base64.b64decode(s['secret'],validate=True)

    def commit_update(self,binding,expected_anchor,new_anchor):
        with _lockfile(self.lock):
            s=self._load();self._check_binding(s,binding)
            if s['anchor']!=expected_anchor.hex():return False
            old=ypb.P2YHostAnchor.FromString(expected_anchor)
            new=ypb.P2YHostAnchor.FromString(new_anchor)
            if (bits(new)!=new_anchor or new.sequence!=old.sequence+1 or
                (new.conversation_id,new.volume_id,new.authority_epoch)!=(old.conversation_id,old.volume_id,old.authority_epoch)):
                raise AuthorityError('ANCHOR_CAS_INVARIANT_FAILED')
            if self.crash_at=='before_host_commit':os._exit(121)
            s['anchor']=new_anchor.hex();self._save(s)
            if self.crash_at=='after_host_commit':os._exit(122)
            return True

    def prepare_reconciliation(self,expected,candidate,record_sha256):
        """Test operator action: issues one-use token. NOT a user-consent UI."""
        if len(record_sha256)!=32:raise AuthorityError('BAD_RECORD_SHA')
        token=secrets.token_bytes(32)
        with _lockfile(self.lock):
            s=self._load()
            if s['revoked'] or s['anchor']!=expected.hex():raise AuthorityError('STALE_APPROVAL')
            s['pending_approval']={'token_sha256':hashlib.sha256(token).hexdigest(),
              'expected':expected.hex(),'candidate':candidate.hex(),'record':record_sha256.hex()}
            self._save(s)
        return token

    def approve_reconciliation(self,binding,expected,proposed,digest,proof):
        with _lockfile(self.lock):
            s=self._load();self._check_binding(s,binding)
            p=s.get('pending_approval')
            if (not p or not proof or s['anchor']!=expected.hex() or
                not hmac.compare_digest(p['token_sha256'],hashlib.sha256(proof).hexdigest()) or
                p['expected']!=expected.hex() or p['candidate']!=proposed.hex() or
                p['record']!=digest.hex()):return False
            old=ypb.P2YHostAnchor.FromString(expected)
            new=ypb.P2YHostAnchor.FromString(proposed)
            if new.sequence!=old.sequence+1 or new.authority_epoch!=old.authority_epoch:
                return False
            s['anchor']=proposed.hex();s['pending_approval']=None;self._save(s)
            return True

    def revoke(self):
        with _lockfile(self.lock):
            s=self._load();s['revoked']=True;s['pending_approval']=None;self._save(s)

    def rotate(self,new_directory):
        """Test-host-driven epoch change; previous key retired, no journal rewrite.

        Caller MUST verify current P2Z.inspect() is CLEAN before invoking.
        """
        with _lockfile(self.lock):
            s=self._load()
            if s['revoked']:raise AuthorityError('REVOKED_EPOCH')
            if Path(new_directory).exists():raise AuthorityError('ROTATED_DIRECTORY_EXISTS')
            if Path(os.path.abspath(new_directory))==Path(s['journal']):raise AuthorityError('REUSED_JOURNAL')
            # Rotate only a fully replayed, clean epoch; never hide a pending tail.
            from cognitum.spatial_host_recovery_readiness import P2ZHostReadiness
            preview=P2ZHostReadiness(s['journal'],host=self).inspect()
            if preview.status!='CLEAN':
                raise AuthorityError('ROTATION_REQUIRES_CLEAN_REPLAY:'+preview.status)
            oldb=self._binding_from(s)
            new_epoch=s['epoch']+1
            if new_epoch >=2**64:raise AuthorityError('EPOCH_EXHAUSTED')
            newa=genesis(s['conversation_id'],s['volume_id'],new_epoch)
            key_id='epoch-'+str(new_epoch)+'-'+secrets.token_hex(8)
            newb=zpb.P2ZHostBinding(schema_version=1,conversation_id=s['conversation_id'],
                volume_id=s['volume_id'],authority_epoch=new_epoch,key_id=key_id,
                external_anchor=bits(newa),research_only=True)
            validate_epoch_transition(oldb,newb,s['journal'],new_directory)
            s['history'].append({'epoch':s['epoch'],'key_id':s['key_id'],
                'retired_anchor_sha256':hashlib.sha256(bytes.fromhex(s['anchor'])).hexdigest(),
                'journal':s['journal']})
            s.update({'epoch':new_epoch,'key_id':key_id,
                'secret':base64.b64encode(secrets.token_bytes(48)).decode(),
                'anchor':bits(newa).hex(),'journal':str(Path(os.path.abspath(new_directory))),
                'pending_approval':None})
            self._save(s)
            return oldb,newb

    @property
    def journal(self):return Path(self._load()['journal'])
