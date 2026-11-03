"""CH33 compactable original CH23 proof journal, research/Linux.

A compacted checkpoint is UNTRUSTED serialized proof source, not proof state.
Every cold recovery recomputes its complete certificate under MPFR. Archived
journal history can be replayed independently using verify_archived_history.
The externally persisted original CH32 head AND checkpoint SHA are necessary
for rollback/tamper detection against a writer that can rewrite all disk data.
An active journal can be bounded; long-term retained external archives cannot.
"""
from __future__ import annotations
import base64, copy, hashlib, json, os, re, sys, time, uuid, zlib
from pathlib import Path
D=Path(__file__).resolve().parent
sys.path[:0]=[str(D.parent/'CH_C14_32'),str(D.parent/'CH_C14_31')]
from journal32 import (ProofJournal, ProgressiveVerifier, GENESIS, VERSION,
                       canonical, digest, _strict_json, _read_frame, _directory_sync,
                       RECORD_RE, PENDING_RE, apply_delta, SimulatedCrash)

SNAPSHOT='checkpoint.json'
SNAPSHOT_TMP=re.compile(r'^\.checkpoint-[0-9a-f]{32}\.pending$')
ARCHIVE_NAME=re.compile(r'^archive_(\d{6})_(\d{6})_([0-9a-f]{64})\.zlib$')
MAX_ARCHIVE_RAW=32*1024*1024
MAX_SNAPSHOT_RAW=8*1024*1024
HEX64=re.compile(r'^[0-9a-f]{64}$')


def _bounded_decompress(data,cap):
    de=zlib.decompressobj()
    decoded=de.decompress(data,cap+1)
    if len(decoded)>cap or de.unconsumed_tail or not de.eof or de.unused_data:
        raise ValueError('Oversized, incomplete or trailing compressed payload')
    return decoded


def _encode_certificate(cert):
    raw=canonical(cert)
    if len(raw)>MAX_SNAPSHOT_RAW:raise ValueError('Checkpoint certificate exceeds bound')
    return base64.b64encode(zlib.compress(raw,9)).decode('ascii')


def _decode_certificate(encoded):
    if not isinstance(encoded,str) or len(encoded)>MAX_SNAPSHOT_RAW*2:
        raise ValueError('Invalid compressed certificate')
    raw=_bounded_decompress(base64.b64decode(encoded,validate=True),MAX_SNAPSHOT_RAW)
    result=_strict_json(raw)
    if canonical(result)!=raw or not isinstance(result,dict):
        raise ValueError('Noncanonical certificate representation')
    return result


def _write_atomic_replace(path,data,crash_at=None):
    """One durable atomic rename; the reader accepts either old or new generation.

    An OS hard-exit before dir-fsync can leave either generation after a power
    failure; OS-exit tests alone cannot establish hardware power-loss safety.
    """
    if len(data)>MAX_SNAPSHOT_RAW:raise ValueError('Snapshot exceeds maximum size')
    tmp=path.parent/f'.checkpoint-{uuid.uuid4().hex}.pending'
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    if crash_at=='before_snapshot_rename':raise SimulatedCrash('Pre-rename checkpoint crash')
    os.replace(tmp,path)
    if crash_at=='after_snapshot_rename':raise SimulatedCrash('After checkpoint rename')
    _directory_sync(path.parent)
    if crash_at=='after_snapshot_fsync':raise SimulatedCrash('After checkpoint fsync')


def _read_envelope(path):
    raw=path.read_bytes()
    if len(raw)>MAX_SNAPSHOT_RAW or not raw.endswith(b'\n'):
        raise ValueError('Truncated or oversized checkpoint')
    obj=_strict_json(raw)
    if not isinstance(obj,dict) or set(obj)!={'body','sha256'} or not isinstance(obj['body'],dict):
        raise ValueError('Checkpoint envelope malformed')
    if obj['sha256']!=digest(obj['body']) or raw!=canonical(obj)+b'\n':
        raise ValueError('Checkpoint hash or canonical encoding invalid')
    return obj


def _archive_name(start,end,sha):return f'archive_{start:06d}_{end:06d}_{sha}.zlib'


def _read_archive(path):
    m=ARCHIVE_NAME.fullmatch(path.name)
    if not m or path.is_symlink() or not path.is_file():raise ValueError('Invalid archive path')
    if path.stat().st_size>MAX_ARCHIVE_RAW:raise ValueError('Archive compressed bytes oversized')
    compressed=path.read_bytes()
    if hashlib.sha256(compressed).hexdigest()!=m.group(3):
        raise ValueError('Archive bytes differ from pinned hash')
    raw=_bounded_decompress(compressed,MAX_ARCHIVE_RAW)
    obj=_strict_json(raw)
    if canonical(obj)!=raw or not isinstance(obj,dict):
        raise ValueError('Archive has malformed or noncanonical bytes')
    if obj.get('range_start')!=int(m.group(1)) or obj.get('range_end')!=int(m.group(2)):
        raise ValueError('Archive range/name mismatch')
    return obj


def _archive_frames(root,archive_dir,start,end,prior_archive_sha,prior_checkpoint_sha,prior_head,prior_checkpoint_envelope):
    """Write a durable immutable, externally stored copy before deleting frames."""
    archive_dir=Path(archive_dir);archive_dir.mkdir(parents=True,exist_ok=True)
    frames=[];head=prior_head
    for n in range(start,end+1):
        p=root/f'{n:06d}.json'
        if not p.is_file() or p.is_symlink():raise ValueError('Missing raw frame for archival')
        entry=_read_frame(p)
        if entry['body']['seq']!=n or entry['body']['prev_sha256']!=head:
            raise ValueError('Invalid frame sequence before archival')
        head=entry['sha256'];frames.append(entry)
    payload={'version':1,'range_start':start,'range_end':end,
             'prior_archive_sha256':prior_archive_sha,
             'prior_checkpoint_sha256':prior_checkpoint_sha,
             'prior_checkpoint_envelope':prior_checkpoint_envelope,
             'prior_head_sha256':prior_head,'final_head_sha256':head,'frames':frames}
    raw=canonical(payload)
    if len(raw)>MAX_ARCHIVE_RAW:raise ValueError('Too much archive data')
    data=zlib.compress(raw,9); sha=hashlib.sha256(data).hexdigest()
    out=archive_dir/_archive_name(start,end,sha)
    if out.exists():
        if out.read_bytes()!=data:raise ValueError('Different bytes under identical archive name')
        return out,sha,frames,head
    tmp=archive_dir/f'.{out.name}-{uuid.uuid4().hex}.pending'
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    # Atomic new creation, never replacing a previously committed archive.
    if out.exists():raise ValueError('Concurrent archive creation')
    os.rename(tmp,out);_directory_sync(archive_dir)
    return out,sha,frames,head


class CompactProofJournal(ProofJournal):
    def __init__(self,path,inp,proto,duals,*,case_id,archive_dir,
                 expected_head_sha256=None,expected_checkpoint_sha256=None,
                 max_active_bytes=None):
        super().__init__(path,inp,proto,duals,case_id=case_id,
                         expected_head_sha256=expected_head_sha256)
        self.archive_dir=Path(archive_dir).resolve()
        self.expected_checkpoint_sha256=expected_checkpoint_sha256
        if max_active_bytes is not None and (type(max_active_bytes) is not int or max_active_bytes<8192):
            raise ValueError('Active disk budget must be at least 8192 bytes')
        self.max_active_bytes=max_active_bytes
        self._checkpoint=None;self._covered=[]
        self.compaction_cpu_seconds=0.0;self.full_mathematical_replay=False

    def recover(self):
        if not (self.path/SNAPSHOT).exists():
            if self.expected_checkpoint_sha256 is not None:
                raise ValueError('Externally pinned checkpoint was removed')
            # CH32 original journal with additional crash-pending checkpoint files.
            # No repair is performed implicitly; pending writes require explicit
            # discard before the next journal append or compact.
            files={};pending=[]
            for p in self.path.iterdir():
                if p.name=='.writer.lock':continue
                if p.is_symlink():raise ValueError('Journal symlink forbidden')
                m=RECORD_RE.fullmatch(p.name)
                if m:files[int(m.group(1))]=p
                elif PENDING_RE.fullmatch(p.name) or SNAPSHOT_TMP.fullmatch(p.name):pending.append(p)
                else:raise ValueError('Unknown un-compacted journal file: '+p.name)
            if sorted(files)!=list(range(len(files))):raise ValueError('Journal sequence missing/gapped')
            session=ProgressiveVerifier();prev=None;head=GENESIS;fresh=0;tick=time.process_time()
            for i in sorted(files):
                e=_read_frame(files[i]);b=e['body']
                if b.get('seq')!=i or b.get('case_id')!=self.case_id or b.get('binding_sha256')!=self._bound() or b.get('prev_sha256')!=head:
                    raise ValueError('Original journal identity/chain mismatch')
                cert=copy.deepcopy(b['payload']) if i==0 else apply_delta(prev,b['payload'])
                if digest(cert)!=b['certificate_sha256'] or len(cert['nodes'])!=b['stage_nodes']:
                    raise ValueError('Original journal proof altered')
                rec=session.verify_stage(cert,self.inp,{**self.proto,'node_budget_per_case':len(cert['nodes'])},self.duals)
                if rec['receipt']['replay_status']!='REPLAYED_BUT_UNRESOLVED':raise ValueError('Original proof verification failed')
                fresh+=rec['receipt']['ancestor_caps_recomputed'];head=e['sha256'];prev=cert
            if self.expected_head_sha256 is not None and head!=self.expected_head_sha256:
                raise ValueError('Original journal head changed from external pin')
            self._checkpoint=None;self._covered=[];self._pending=pending
            self.session=session;self.cert=prev;self.head=head;self.seq=len(files)
            self.recovery_fresh=fresh;self.recovery_cpu_seconds=time.process_time()-tick
            return {'stages_verified':len(files),'fresh_bounds':fresh,'head_sha256':head,
                    'uncommitted_pending':len(pending),'recovery_cpu_seconds':self.recovery_cpu_seconds,
                    'cached_state_imported':False}
        start=time.process_time()
        cp=_read_envelope(self.path/SNAPSHOT);b=cp['body']
        expected={'version','kind','case_id','binding_sha256','upto_seq','head_sha256',
                  'stage_nodes','certificate_sha256','compressed_certificate',
                  'prior_checkpoint_sha256','prior_archive_sha256','archive_sha256',
                  'archive_file','prior_head_sha256','range_start','covered_hashes'}
        if set(b)!=expected or b['version']!=1 or b['kind']!='compacted_checkpoint' or \
                b['case_id']!=self.case_id or b['binding_sha256']!=self._bound():
            raise ValueError('Wrong compacted checkpoint identity, schema or binding')
        if (self.expected_checkpoint_sha256 is not None and
                cp['sha256']!=self.expected_checkpoint_sha256):
            raise ValueError('Compacted checkpoint differs from external pin')
        if not isinstance(b['upto_seq'],int) or b['upto_seq']<0 or \
                not isinstance(b['range_start'],int) or b['range_start']>b['upto_seq']:
            raise ValueError('Compaction range invalid')
        if not HEX64.fullmatch(b['head_sha256']) or not HEX64.fullmatch(b['archive_sha256']):
            raise ValueError('Malformed hash')
        if not isinstance(b['covered_hashes'],dict) or list(sorted(map(int,b['covered_hashes'])))!=list(range(b['range_start'],b['upto_seq']+1)):
            raise ValueError('Incomplete covered-frame digests')
        cert=_decode_certificate(b['compressed_certificate'])
        if len(cert.get('nodes',[]))!=b['stage_nodes'] or digest(cert)!=b['certificate_sha256']:
            raise ValueError('Snapshot proof content altered')
        archive=self.archive_dir/b['archive_file']
        if archive.name!=_archive_name(b['range_start'],b['upto_seq'],b['archive_sha256']):
            raise ValueError('Unsafe archive locator')
        obj=_read_archive(archive)
        if (obj.get('prior_archive_sha256')!=b['prior_archive_sha256'] or
            obj.get('prior_checkpoint_sha256')!=b['prior_checkpoint_sha256'] or
            (obj['prior_checkpoint_envelope']['sha256'] if obj.get('prior_checkpoint_envelope') else GENESIS)!=b['prior_checkpoint_sha256'] or
            (obj.get('prior_checkpoint_envelope') is not None and
             digest(obj['prior_checkpoint_envelope']['body'])!=obj['prior_checkpoint_envelope']['sha256']) or
            obj.get('prior_head_sha256')!=b['prior_head_sha256'] or
            obj.get('final_head_sha256')!=b['head_sha256'] or
            len(obj.get('frames',[]))!=b['upto_seq']-b['range_start']+1):
            raise ValueError('Compaction archive chain mismatch')
        for i,e in enumerate(obj['frames'],b['range_start']):
            if e['sha256']!=b['covered_hashes'].get(str(i)) or e['sha256']!=digest(e['body']):
                raise ValueError('Compacted frame digest disagrees with archive')
        # The persisted checkpoint is untrusted. Cold replay is mandatory.
        session=ProgressiveVerifier()
        receipt=session.verify_stage(cert,self.inp,{**self.proto,'node_budget_per_case':len(cert['nodes'])},self.duals)
        if receipt['receipt']['replay_status']!='REPLAYED_BUT_UNRESOLVED':
            raise ValueError('Compacted certificate not independently verified')
        fresh=receipt['receipt']['ancestor_caps_recomputed'];head=b['head_sha256'];prev=cert
        covered=[];tail={};pending=[]
        for p in self.path.iterdir():
            if p.name in ('.writer.lock',SNAPSHOT):continue
            if p.is_symlink():raise ValueError('Journal symlink forbidden')
            m=RECORD_RE.fullmatch(p.name)
            if m:
                idx=int(m.group(1))
                if idx<=b['upto_seq']:
                    if idx<b['range_start'] or str(idx) not in b['covered_hashes'] or \
                            _read_frame(p)['sha256']!=b['covered_hashes'][str(idx)]:
                        raise ValueError('Covered frame has unexpected contents')
                    covered.append(p)
                else:tail[idx]=p
            elif SNAPSHOT_TMP.fullmatch(p.name) or PENDING_RE.fullmatch(p.name):pending.append(p)
            else:raise ValueError('Unknown compacted journal file: '+p.name)
        if sorted(tail)!=list(range(b['upto_seq']+1,b['upto_seq']+1+len(tail))):
            raise ValueError('Tail frames are gapped or reordered')
        for idx in sorted(tail):
            e=_read_frame(tail[idx]);body=e['body']
            if body.get('seq')!=idx or body.get('prev_sha256')!=head or \
                    body.get('binding_sha256')!=self._bound() or body.get('case_id')!=self.case_id:
                raise ValueError('Tail frame identity/chain invalid')
            nxt=apply_delta(prev,body['payload'])
            if digest(nxt)!=body['certificate_sha256'] or len(nxt['nodes'])!=body['stage_nodes']:
                raise ValueError('Tail proof digest invalid')
            rec=session.verify_stage(nxt,self.inp,{**self.proto,'node_budget_per_case':len(nxt['nodes'])},self.duals)
            if rec['receipt']['replay_status']!='REPLAYED_BUT_UNRESOLVED':
                raise ValueError('Tail extension mathematical replay failed')
            fresh+=rec['receipt']['ancestor_caps_recomputed']
            head=e['sha256'];prev=nxt
        if self.expected_head_sha256 is not None and head!=self.expected_head_sha256:
            raise ValueError('Original journal head differs from external pin')
        self.session=session;self.cert=prev;self.head=head;self.seq=b['upto_seq']+1+len(tail)
        self._checkpoint=cp;self._covered=covered;self._pending=pending
        self.recovery_fresh=fresh;self.recovery_cpu_seconds=time.process_time()-start
        self.full_mathematical_replay=True
        self.verify_archive_chain_metadata()
        return {'stages_verified':len(tail)+1,'fresh_bounds':fresh,
                'checkpoint_sha256':cp['sha256'],'head_sha256':head,
                'recovery_cpu_seconds':self.recovery_cpu_seconds,
                'uncommitted_pending':len(pending),'covered_frame_remnants':len(covered),
                'cached_state_imported':False}

    def _active_bytes(self):
        return sum(p.stat().st_size for p in self.path.iterdir() if p.is_file())

    def append(self,cert,*,crash_at=None):
        if self._covered:raise ValueError('Remove verified covered remnants before writing')
        if self.max_active_bytes is not None and self.cert is not None and digest(cert)!=digest(self.cert):
            # Conservative reservation for one future envelope; compaction
            # occurs BEFORE a new frame can exceed the configured budget.
            import journal32
            delta=journal32.make_delta(self.cert,cert)
            projected=len(canonical(delta))+2048
            if self._active_bytes()+projected>self.max_active_bytes:
                self.compact()
            if self._active_bytes()+projected>self.max_active_bytes:
                raise ValueError('Next extension cannot fit active journal byte budget')
        elif self.max_active_bytes is not None and self.cert is None:
            if len(canonical(cert))+2048>self.max_active_bytes:
                raise ValueError('Genesis proof cannot fit active journal budget')
        result=super().append(cert,crash_at=crash_at)
        if self.max_active_bytes is not None and self._active_bytes()>self.max_active_bytes:
            raise RuntimeError('Active byte-budget accounting invariant violated')
        return result

    def discard_pending(self):
        if self._lock_fd is None:raise RuntimeError('Exclusive lock required')
        if self._poisoned:raise RuntimeError('A failed writer must cold-recover before repair')
        for p in self._pending:
            if not (PENDING_RE.fullmatch(p.name) or SNAPSHOT_TMP.fullmatch(p.name)):
                raise ValueError('Unknown uncommitted pending file')
            if p.is_symlink():raise ValueError('Pending symlink forbidden')
        for p in self._pending:p.unlink()
        n=len(self._pending)
        if n:_directory_sync(self.path)
        self._pending=[]
        return n

    def cleanup_covered(self,*,crash_after=None):
        if self._lock_fd is None:raise RuntimeError('Exclusive lock required')
        if self._checkpoint is None:return 0
        if self._pending:raise ValueError('Explicitly discard pending writes before cleanup')
        n=0
        for p in list(self._covered):
            p.unlink();n+=1
            if crash_after is not None and n>=crash_after:
                self._poisoned=True;raise SimulatedCrash('Hard crash while pruning covered frames')
        if n:_directory_sync(self.path)
        self._covered=[]
        return n

    def compact(self,*,crash_at=None,cleanup=True):
        if self._lock_fd is None:raise RuntimeError('Exclusive writer lock required')
        if self._poisoned or self._pending or self._covered:
            raise ValueError('Journal must be clean and recovered before compaction')
        if not self.cert:raise ValueError('Cannot compact empty proof journal')
        prev_cp=self._checkpoint
        start=prev_cp['body']['upto_seq']+1 if prev_cp else 0
        end=self.seq-1
        if start>end:raise ValueError('No new committed extensions to compact')
        ar=self.archive_dir
        if ar==self.path.resolve() or self.path.resolve() in ar.parents or ar in self.path.resolve().parents:
            raise ValueError('External archive must not share journal subtree')
        tick=time.process_time()
        prior_archive=prev_cp['body']['archive_sha256'] if prev_cp else GENESIS
        prior_cp=prev_cp['sha256'] if prev_cp else GENESIS
        prior_head=prev_cp['body']['head_sha256'] if prev_cp else GENESIS
        arch_path,sha,frames,arch_head=_archive_frames(self.path,ar,start,end,prior_archive,prior_cp,prior_head,prev_cp)
        if arch_head!=self.head:raise ValueError('Archive does not end at verified head')
        body={'version':1,'kind':'compacted_checkpoint','case_id':self.case_id,
              'binding_sha256':self._bound(),'upto_seq':end,'head_sha256':self.head,
              'stage_nodes':len(self.cert['nodes']),'certificate_sha256':digest(self.cert),
              'compressed_certificate':_encode_certificate(self.cert),
              'prior_checkpoint_sha256':prior_cp,'prior_archive_sha256':prior_archive,
              'archive_sha256':sha,'archive_file':arch_path.name,
              'prior_head_sha256':prior_head,'range_start':start,
              'covered_hashes':{str(start+i):e['sha256'] for i,e in enumerate(frames)}}
        entry={'body':body,'sha256':digest(body)}
        if self.max_active_bytes is not None and len(canonical(entry))+1>self.max_active_bytes:
            raise ValueError('Checkpoint exceeds active disk budget')
        try:
            _write_atomic_replace(self.path/SNAPSHOT,canonical(entry)+b'\n',crash_at=crash_at)
        except BaseException:
            self._poisoned=True
            raise
        self._checkpoint=entry
        self._covered=[self.path/f'{i:06d}.json' for i in range(start,end+1)]
        if crash_at=='during_prune':self.cleanup_covered(crash_after=1)
        removed=self.cleanup_covered() if cleanup else 0
        self.compaction_cpu_seconds=time.process_time()-tick
        return {'checkpoint_sha256':entry['sha256'],'head_sha256':self.head,
                'compacted_frames':end-start+1,'checkpoint_nodes':len(self.cert['nodes']),
                'archive_sha256':sha,'archive_file':arch_path.name,
                'covered_files_removed':removed,'active_bytes':sum(p.stat().st_size for p in self.path.iterdir() if p.is_file()),
                'archive_bytes':arch_path.stat().st_size,
                'recovery_requires_fresh_MPFR':True,'cpu_seconds':self.compaction_cpu_seconds}

    def verify_archive_chain_metadata(self):
        """Verify availability/cryptographic linkage of every compacted epoch.

        Does NOT substitute for verify_archived_history's full MPFR checks.
        """
        if self._checkpoint is None:raise ValueError('No compacted checkpoint')
        cp=self._checkpoint;count=0;last_end=cp['body']['upto_seq']
        while True:
            b=cp['body'];h=b['archive_sha256'];end=b['upto_seq']
            matches=[p for p in self.archive_dir.glob(f'archive_*_{end:06d}_{h}.zlib')
                     if ARCHIVE_NAME.fullmatch(p.name)]
            if len(matches)!=1:raise ValueError('Missing or duplicated history archive')
            p=matches[0];arch=_read_archive(p)
            if arch['range_start']!=b['range_start'] or arch['range_end']!=end or \
               arch['final_head_sha256']!=b['head_sha256'] or \
               arch['prior_checkpoint_sha256']!=b['prior_checkpoint_sha256'] or \
               arch['prior_archive_sha256']!=b['prior_archive_sha256']:
                raise ValueError('Archive history metadata mismatch')
            count+=1;prior=arch.get('prior_checkpoint_envelope')
            if prior is None:
                if b['range_start']!=0 or b['prior_checkpoint_sha256']!=GENESIS or \
                   b['prior_archive_sha256']!=GENESIS:
                    raise ValueError('Archive chain genesis invalid')
                break
            if prior.get('sha256')!=digest(prior.get('body')) or \
               prior['sha256']!=b['prior_checkpoint_sha256'] or \
               prior['body']['upto_seq']+1!=b['range_start'] or \
               prior['body']['head_sha256']!=b['prior_head_sha256']:
                raise ValueError('Archived checkpoint link altered')
            cp=prior
        return {'archive_epochs':count,'upto_seq':last_end,'hash_chain_complete':True,
                'mathematics_verified_by_this_check':False}

    def verify_archived_history(self):
        """Independently replay every archived historical MPFR proof in a NEW session.

        All archive generations are linked to their complete checkpoint envelopes.
        This is intentionally more expensive than verifying just the final snapshot.
        """
        if self._checkpoint is None:raise ValueError('No compaction exists')
        current_cp=self._checkpoint
        archives=[];seen=set();head_archive=current_cp['body']['archive_sha256']
        next_cp=current_cp
        while True:
            ending=next_cp['body']['upto_seq']
            matches=[p for p in self.archive_dir.glob(f'archive_*_{ending:06d}_{head_archive}.zlib')
                     if ARCHIVE_NAME.fullmatch(p.name)]
            if len(matches)!=1 or matches[0] in seen:
                raise ValueError('Missing, duplicate or circular archive checkpoint')
            path=matches[0];seen.add(path);obj=_read_archive(path)
            if obj['final_head_sha256']!=next_cp['body']['head_sha256'] or \
               obj['range_start']!=next_cp['body']['range_start'] or \
               obj['range_end']!=next_cp['body']['upto_seq'] or \
               hashlib.sha256(path.read_bytes()).hexdigest()!=next_cp['body']['archive_sha256']:
                raise ValueError('Archived checkpoint head/range mismatch')
            prior_cp=obj.get('prior_checkpoint_envelope')
            if prior_cp is None:
                if (obj['prior_checkpoint_sha256']!=GENESIS or
                    obj['prior_archive_sha256']!=GENESIS or
                    obj['range_start']!=0 or obj['prior_head_sha256']!=GENESIS):
                    raise ValueError('Archive genesis missing')
                archives.append((path,obj));break
            if not isinstance(prior_cp,dict) or prior_cp.get('sha256')!=digest(prior_cp.get('body')):
                raise ValueError('Prior checkpoint commitment altered')
            if prior_cp['sha256']!=obj['prior_checkpoint_sha256'] or \
               prior_cp['sha256']!=next_cp['body']['prior_checkpoint_sha256'] or \
               prior_cp['body']['archive_sha256']!=obj['prior_archive_sha256'] or \
               prior_cp['body']['head_sha256']!=obj['prior_head_sha256'] or \
               prior_cp['body']['upto_seq']+1!=obj['range_start']:
                raise ValueError('Prior checkpoint archive linkage broken')
            archives.append((path,obj))
            next_cp=prior_cp;head_archive=prior_cp['body']['archive_sha256']
        archives.reverse()
        session=ProgressiveVerifier();prev=None;head=GENESIS;frames=0
        for path,obj in archives:
            for e in obj['frames']:
                body=e['body']
                if e['sha256']!=digest(body) or body['seq']!=frames or \
                   body['prev_sha256']!=head or body['binding_sha256']!=self._bound() or \
                   body['case_id']!=self.case_id:
                    raise ValueError('Archived frame hash/sequence/binding altered')
                cert=copy.deepcopy(body['payload']) if frames==0 else apply_delta(prev,body['payload'])
                if digest(cert)!=body['certificate_sha256'] or len(cert['nodes'])!=body['stage_nodes']:
                    raise ValueError('Archived mathematical certificate altered')
                receipt=session.verify_stage(cert,self.inp,{**self.proto,'node_budget_per_case':len(cert['nodes'])},self.duals)
                if receipt['receipt']['replay_status']!='REPLAYED_BUT_UNRESOLVED':
                    raise ValueError('Archived proof failed independent MPFR replay')
                head=e['sha256'];prev=cert;frames+=1
            if head!=obj['final_head_sha256']:raise ValueError('Archive final head mismatch')
        live=self._checkpoint['body']
        if frames!=live['upto_seq']+1 or head!=live['head_sha256'] or digest(prev)!=live['certificate_sha256']:
            raise ValueError('Historical mathematics does not match live checkpoint')
        return {'replayed_frames':frames,'archives':len(archives),'final_original_head_sha256':head,
                'archived_history_reverified_with_MPFR':True,'checkpoint_sha256':self._checkpoint['sha256']}
