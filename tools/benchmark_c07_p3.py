"""Deterministic C07 P3 *synthetic* replay/CAS cost comparison.

The naive latest-write-wins dictionary is intentionally unsafe and is NOT a
candidate production engine. No Lu model is executed. Times are local wall
clock diagnostic values, not accuracy or generalization claims.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import platform
import statistics
import tempfile
from time import perf_counter

from cognitum.proto import state_pb2 as pb
from cognitum.state_journal import StateJournal
from cognitum.state_revision import StateLedger, StateConflict


def sample_events(size=32):
    if not (2 <= size <= 64):
        raise ValueError('fixture size must be 2..64')
    result=[]
    for index in range(size):
        item=pb.StateEvent(schema_version=1,event_id=f'assert{index}',scope_id='bench',
            claim_id=f'claim{index}',subject_id=f'subject{index//2}',predicate='goal',
            value_kind=pb.TEXT,value_text=f'draft{index}',origin=pb.USER_VERIFIED,
            action=pb.ASSERT,expected_revision=0,
            recorded_at_ms=1000+index,effective_at_ms=1000+index,
            source=pb.SourceEvidence(session_id='benchsession',root_entry_id='1',
                revision_entry_id='2',content_sha256='a'*64,snapshot_id='synthetic1'))
        result.append(item)
    for index in range(0,size,2):
        updated=pb.StateEvent()
        updated.CopyFrom(result[index])
        updated.event_id=f'update{index}'
        updated.action=pb.SUPERSEDE
        updated.expected_revision=1
        updated.value_text=f'final{index}'
        updated.recorded_at_ms=3000+index
        updated.effective_at_ms=3000+index
        result.append(updated)
    stale=pb.StateEvent()
    stale.CopyFrom(result[-1])
    stale.event_id='stale-final'
    stale.value_text='should-not-win'
    return result,stale


class SyntheticLease:
    """Not a credential. Benchmark-only simulation of a Lu host lease."""
    def ensure_active(self): return True
    def admit_event(self, scope, event):
        return scope=='bench' and event.scope_id=='bench' and event.origin==pb.USER_VERIFIED
    def verify_source(self, scope, source, require_current):
        return (scope=='bench' and source.session_id=='benchsession'
                and source.revision_entry_id=='2' and source.content_sha256=='a'*64
                and source.snapshot_id=='synthetic1')


def diagnostic(size=32,repeats=3):
    events,stale=sample_events(size)
    frames=[e.SerializeToString(deterministic=True) for e in events]
    source_hash=sha256(b''.join(frames)).hexdigest()
    naive_ms=[]; reducer_ms=[]; journal_ms=[]
    for _ in range(repeats):
        start=perf_counter()
        current={}
        for event in [*events,stale]: current[event.claim_id]=event.value_text
        naive_ms.append((perf_counter()-start)*1000)
        start=perf_counter()
        ledger=StateLedger('bench')
        ledger.apply_batch(events)
        try:
            ledger.apply(stale)
            raise AssertionError('CAS unexpectedly accepted stale event')
        except StateConflict:
            pass
        projection=ledger.projection()
        reducer_ms.append((perf_counter()-start)*1000)
        with tempfile.TemporaryDirectory(prefix='cognitum-bench-') as temp:
            path=Path(temp)/'state.sqlite'
            start=perf_counter()
            with StateJournal(path,'bench') as writer:
                receipt=writer.apply_host_batch(events,SyntheticLease())
            with StateJournal(path,'bench') as reader:
                released=[]
                reader.publish_host_fenced(SyntheticLease(),released.append)
                assert reader.head()[0]==len(events)
                frame=pb.StateProjection.FromString(released[0])
            journal_ms.append((perf_counter()-start)*1000)
            assert frame==projection and receipt.applied==len(events)
    return {
        'tier':'synthetic_reference_only',
        'Lu_or_model_executed':False,
        'size':size,'events':len(events),'attempted_stale':1,
        'stale_attempt_rejected_by_C07':True,
        'naive_stale_attempt_wrongly_overwrote_claim':current[stale.claim_id]=='should-not-win',
        'C07_conflict_edges_preserved':len(projection.conflicts),
        'replayed_projection_matches':True,
        'fixture_sha256':source_hash,
        'median_ms':{'naive_dictionary':round(statistics.median(naive_ms),3),
                     'C07_in_memory':round(statistics.median(reducer_ms),3),
                     'C07_SQLite_commit_restart_verify':round(statistics.median(journal_ms),3)},
        'environment':{'python':platform.python_version(),'platform':platform.platform()},
        'caveat':'Synthetic microbenchmark only; naive baseline omits authorization, durability and provenance; not comparable product throughput or Lu model accuracy.'
    }


if __name__=='__main__':
    print(json.dumps(diagnostic(),indent=2,sort_keys=True))
