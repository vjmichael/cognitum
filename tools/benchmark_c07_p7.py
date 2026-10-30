"""Run C07 P7 multi-conversation labeled replay; synthetic offline data only."""
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
from cognitum.state_journal import StateJournal
from cognitum.state_longform_eval import (
    SCOPE, evaluate, expected, filtered_projection, long_scenarios, query,
)


class _SyntheticLease:
    """Exact-frame fixture. It is emphatically NOT an authenticated host lease."""
    def __init__(self, events):
        self.records={e.source.SerializeToString(deterministic=True):
            e.SerializeToString(deterministic=True) for e in events}
        self.active=True
        self.deleted=set()
        self.verified=0

    def ensure_active(self):return self.active

    def admit_event(self, scope, event):
        source=event.source.SerializeToString(deterministic=True)
        return (self.active and scope==SCOPE and event.scope_id==SCOPE and
                self.records.get(source)==event.SerializeToString(deterministic=True))

    def verify_source(self, scope, source, require_current):
        self.verified+=1
        raw=source.SerializeToString(deterministic=True)
        return self.active and scope==SCOPE and raw in self.records and raw not in self.deleted


def benchmark(repeats: int = 2) -> dict:
    if type(repeats) is not int or not 1<=repeats<=5:
        raise ValueError('repeats must be integer from 1 through 5')
    result=evaluate()
    if result['C07_oracle_mismatches']:
        raise AssertionError('labeled C07 oracle disagreement')
    counts=0
    denied_deletion=denied_revocation=0
    verification_count=0
    timing={'commit_ms':[],'restart_ms':[],'fenced_query_ms':[]}
    bytes_on_disk=[]
    for scenario in long_scenarios():
        for _ in range(repeats):
            lease=_SyntheticLease(scenario.events)
            with tempfile.TemporaryDirectory(prefix='c07-p7-') as d:
                path=Path(d)/'derived.sqlite'
                begin=perf_counter_ns()
                with StateJournal(path,SCOPE) as journal:
                    receipt=journal.apply_host_batch(scenario.events,lease)
                    if receipt.applied != len(scenario.events):
                        raise AssertionError('missing journal events')
                timing['commit_ms'].append((perf_counter_ns()-begin)/1e6)
                begin=perf_counter_ns()
                with StateJournal(path,SCOPE) as journal:
                    timing['restart_ms'].append((perf_counter_ns()-begin)/1e6)
                    for case in scenario.cases:
                        begin=perf_counter_ns()
                        answer=journal.publish_host_as_of(query(case),lease,
                            lambda data:pb.HistoricalProjection.FromString(data))
                        timing['fenced_query_ms'].append((perf_counter_ns()-begin)/1e6)
                        if filtered_projection(answer,scenario.subject_id)!=expected(case):
                            raise AssertionError('reopened journal oracle mismatch: '+scenario.name+'/'+case.name)
                        counts+=1
                    # An unrelated chat's source must also be valid, not just target claims.
                    unrelated=next(e for e in scenario.events if e.predicate=='background_setting')
                    lease.deleted.add(unrelated.source.SerializeToString(deterministic=True))
                    out=[]
                    try:
                        journal.publish_host_as_of(query(scenario.cases[-1]),lease,out.append)
                    except SourceUnavailable:denied_deletion+=1
                    else:raise AssertionError('deleted background source leaked')
                    if out:raise AssertionError('unauthorized publication callback ran')
                    lease.deleted.clear();lease.active=False
                    try:
                        journal.publish_host_as_of(query(scenario.cases[-1]),lease,out.append)
                    except SourceUnavailable:denied_revocation+=1
                    else:raise AssertionError('revoked synthetic lease leaked')
                    if out:raise AssertionError('revocation publication callback ran')
                    verification_count+=lease.verified
                bytes_on_disk.append(path.stat().st_size)
    return {**result,'repeats':repeats,'restarted_journal_labeled_queries':counts,
            'deleted_background_denials':denied_deletion,
            'revoked_lease_denials':denied_revocation,
            'source_checks':verification_count,
            'median_diagnostic_ms':{key:round(median(v),4) for key,v in timing.items()},
            'median_sqlite_file_bytes':int(median(bytes_on_disk)),
            'environment':{'python':platform.python_version(),'os':platform.system(),
                           'machine':platform.machine()},
            'timing_caveats':['Timing samples are Python/SQLite synthetic diagnostics, not throughput or matched-cost comparisons.',
                'Fixture sources are not real ANSF ownership, current-revision or user authentication.',
                'No model, native Rust, Windows Lu integration or external evaluator participated.']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repeats',type=int,default=2)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    data=benchmark(args.repeats)
    text=json.dumps(data,sort_keys=True,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text,encoding='utf-8')
    print(text)

if __name__=='__main__': main()
