"""C07 P6 — hand-labelled correctness and *non-comparable* timing diagnostics.

No Lu or model runs. Direct Python baseline functions do not implement source
verification, authorization, durable recovery, or the complete C07 semantics.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
from statistics import median
import tempfile
from time import perf_counter_ns

from cognitum.proto import state_pb2 as pb
from cognitum.state_host_gate import SourceUnavailable
from cognitum.state_evaluation import (
    SCOPE, golden_scenarios, evaluate, query, expected, observed,
    chronological_register, effective_clock_register,
)
from cognitum.state_journal import StateJournal
from cognitum.state_revision import StateLedger
from cognitum.state_temporal import project_as_of


class FixtureLease:
    """Synthetic benchmark lease: NEVER a Lu credential or an authorization grant."""
    def __init__(self, events):
        self.sources = {e.source.SerializeToString(deterministic=True) for e in events}
        self.active = True
        self.deleted = set()
        self.verified = 0

    def ensure_active(self):
        return self.active

    def admit_event(self, scope, event):
        return scope == SCOPE and event.scope_id == SCOPE and event.source.SerializeToString(deterministic=True) in self.sources

    def verify_source(self, scope, source, require_current):
        self.verified += 1
        blob = source.SerializeToString(deterministic=True)
        return scope == SCOPE and self.active and blob in self.sources and blob not in self.deleted


def _ms(nanos):
    return round(nanos / 1_000_000, 4)


def benchmark(repeats: int = 3) -> dict:
    if not isinstance(repeats,int) or repeats < 1 or repeats > 10:
        raise ValueError('repeats must be in 1..10')
    scenario_list = golden_scenarios()
    analysis = evaluate()
    if analysis['C07_oracle_mismatches']:
        raise AssertionError('C07 failed a hand-labelled historical oracle')
    counts = 0
    timing = {key:[] for key in ('chronological_query', 'effective_clock_query',
            'C07_in_memory_query', 'C07_SQLite_commit',
            'C07_SQLite_restart', 'C07_SQLite_fenced_query')}
    disk_bytes=[]
    canonical_frames=[]
    for scenario in scenario_list:
        canonical_frames.extend(e.SerializeToString(deterministic=True) for e in scenario.events)
        for repeat in range(repeats):
            lease = FixtureLease(scenario.events)
            ledger = StateLedger(SCOPE)
            ledger.apply_batch(scenario.events)
            with tempfile.TemporaryDirectory(prefix='c07-p6-') as d:
                path=Path(d)/'derived.sqlite'
                start=perf_counter_ns()
                with StateJournal(path,SCOPE) as journal:
                    journal.apply_host_batch(scenario.events,lease)
                timing['C07_SQLite_commit'].append(perf_counter_ns()-start)
                start=perf_counter_ns()
                with StateJournal(path,SCOPE) as journal:
                    timing['C07_SQLite_restart'].append(perf_counter_ns()-start)
                    for case in scenario.cases:
                        counts += 1
                        start=perf_counter_ns()
                        chronological_register(scenario.events,case)
                        timing['chronological_query'].append(perf_counter_ns()-start)
                        start=perf_counter_ns()
                        effective_clock_register(scenario.events,case)
                        timing['effective_clock_query'].append(perf_counter_ns()-start)
                        start=perf_counter_ns()
                        in_mem=project_as_of(ledger,query(case))
                        timing['C07_in_memory_query'].append(perf_counter_ns()-start)
                        start=perf_counter_ns()
                        delivered=journal.publish_host_as_of(query(case),lease,
                            lambda raw:pb.HistoricalProjection.FromString(raw))
                        timing['C07_SQLite_fenced_query'].append(perf_counter_ns()-start)
                        if observed(delivered)!=expected(case) or delivered!=in_mem:
                            raise AssertionError('journal restart diverged from oracle: '+scenario.name+'/'+case.name)
                    # Verify fail-closed behavior after modelled host deletion.
                    lease.deleted.add(next(iter(lease.sources)))
                    try:
                        journal.publish_host_as_of(query(scenario.cases[0]),lease,lambda raw:raw)
                    except SourceUnavailable:
                        pass
                    else:
                        raise AssertionError('deleted source disclosed historical state')
                    lease.active=False
                    try:
                        journal.publish_host_as_of(query(scenario.cases[0]),lease,lambda raw:raw)
                    except SourceUnavailable:
                        pass
                    else:
                        raise AssertionError('revoked lease disclosed historical state')
                disk_bytes.append(path.stat().st_size)
    return {**analysis,
        'journal_restart_oracle_queries':counts,
        'deleted_evidence_and_revoked_lease_denial':True,
        'synthetic_fixture_event_frames_sha256':sha256(b''.join(
            len(x).to_bytes(4,'big')+x for x in canonical_frames)).hexdigest(),
        'timing_ms_median':{key:_ms(median(values)) for key,values in timing.items()},
        'persisted_sqlite_file_bytes_median':int(median(disk_bytes)),
        'repeats':repeats,'measurement_environment':{
            'python':platform.python_version(),'platform':platform.platform()},
        'timing_caveats':[
            'Medians are diagnostic, order-dependent, single-process local timings with tiny synthetic inputs.',
            'Baselines do not pay for Protobuf, SQLite, crash recovery, source verification or authorization.',
            'C07 journal timings include Python replay, SQLite transaction, and synthetic callback overhead.',
            'SQLite on-disk bytes exclude any optional external Lu canonical ANSF database and backups.',
            'No real model, Windows x86-64 Lu host, or hardware-controlled performance run.'
        ]}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repeats',type=int,default=3)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    result=benchmark(args.repeats)
    payload=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(payload,encoding='utf-8')
    print(payload)

if __name__=='__main__':
    main()
