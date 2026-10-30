"""Offline Linux synthetic journal commit/recovery overhead; no Lu integration."""
import argparse
import json
import os
from pathlib import Path
import statistics
import tempfile
import time

from cognitum.spatial_durable_incremental_volume import P2YDurableSession,genesis,bits
from cognitum.spatial_incremental_volume import P2XSession
from cognitum.proto import spatial_durable_incremental_volume_pb2 as yp
from cognitum.spatial_map_lifecycle import advance as full_advance
from tests.test_c15_t3_p2w_map_lifecycle import request,next_source
from tests.test_c15_t3_p2v_dynamic_scene_robustness import fixture

class MockHost:
    def __init__(self, initial):self.anchor=yp.P2YHostAnchor();self.anchor.CopyFrom(initial)
    def read(self):x=yp.P2YHostAnchor();x.CopyFrom(self.anchor);return x
    def compare_and_swap(self, old,new):
        if bits(old)!=bits(self.anchor):return False
        self.anchor.CopyFrom(new);return True

def main():
    p=argparse.ArgumentParser();p.add_argument('--rounds',type=int,default=5);p.add_argument('--out',required=True)
    args=p.parse_args();assert 1<=args.rounds<=20
    q1=request()
    first=full_advance(q1)
    q2=request(next_source(fixture()),previous=first.checkpoint,sequence=2)
    direct=[]; journal=[]; recover=[]; disk=[]
    for _ in range(args.rounds):
        t=time.perf_counter_ns()
        ephemeral=P2XSession()
        a=ephemeral.advance(q1,validate_parity=True)
        b=ephemeral.advance(q2,validate_parity=True)
        direct.append((time.perf_counter_ns()-t)/1e6)
        with tempfile.TemporaryDirectory() as tmp:
            host=MockHost(genesis(q1.source_request.dynamic_request.conversation_id,
                                  q1.source_request.dynamic_request.volume_id,11))
            t=time.perf_counter_ns()
            durable=P2YDurableSession(tmp+'/records',host_secret=b'p2y-profiling-only-not-a-host-key-0123456789',authority=host)
            a2=durable.advance(q1);b2=durable.advance(q2)
            journal.append((time.perf_counter_ns()-t)/1e6)
            assert bits(a2.lifecycle)==bits(a.lifecycle) and bits(b2.lifecycle)==bits(b.lifecycle)
            disk.append(sum(x.stat().st_size for x in Path(tmp+'/records').glob('*.p2y')))
            t=time.perf_counter_ns()
            restored=P2YDurableSession(tmp+'/records',host_secret=b'p2y-profiling-only-not-a-host-key-0123456789',authority=host)
            recover.append((time.perf_counter_ns()-t)/1e6)
            assert bits(restored.anchor)==bits(host.anchor)
    out={
      'milestone':'C15 T3 P2Y','environment':'local Linux synthetic fixture',
      'rounds':args.rounds,'update_count_per_round':2,
      'verification':'P2Y recovered both records with exact deterministic P2W parity',
      'median_direct_p2x_full_replay_ms':round(statistics.median(direct),3),
      'median_p2y_fsync_plus_authority_ms':round(statistics.median(journal),3),
      'median_p2y_restart_reverification_ms':round(statistics.median(recover),3),
      'journal_disk_bytes_for_two_records':disk[0],
      'all_measurements_ms':{'p2x':direct,'journal':journal,'recovery':recover},
      'excluded':'sensor processing, Windows storage, real host persistence, OS crash simulation, network I/O',
      'interpretation':'This is an experimental durability overhead measurement, not a speedup or production certification.'
    }
    Path(args.out).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
