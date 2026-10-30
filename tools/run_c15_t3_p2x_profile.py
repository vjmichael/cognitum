"""P2X same-input/full-replay timing comparison on synthetic sliding windows.

PYTHONPATH=. python tools/run_c15_t3_p2x_profile.py --out /tmp/p2x-profile.json
"""
from __future__ import annotations
import argparse
import json
import platform
from pathlib import Path
import statistics
import time
import sys

from tests.test_c15_t3_p2v_dynamic_scene_robustness import fixture
from tests.test_c15_t3_p2u_dynamic_scene_mapping import shifted
from tests.test_c15_t3_p2w_map_lifecycle import request
from cognitum.spatial_map_lifecycle import advance as full_advance
from cognitum.spatial_incremental_volume import P2XSession


def build_sources():
    base=fixture()
    result=[]
    for i in range(4):
        if i:
            base.dynamic_request.windows.add().CopyFrom(shifted(base.dynamic_request.windows[0],200*i))
        result.append(request(base))
    return result


def run(sources):
    engine=P2XSession()
    full_previous=None
    fast_previous=None
    full_times=[]
    fast_times=[]
    step_stats=[]
    for idx,prepared in enumerate(sources):
        from cognitum.proto import spatial_map_lifecycle_pb2 as lp
        full=lp.P2WUpdateRequest();full.CopyFrom(prepared)
        fast=lp.P2WUpdateRequest();fast.CopyFrom(prepared)
        for r,prior in ((full,full_previous),(fast,fast_previous)):
            r.sequence=idx+1
            if prior is not None:r.previous.CopyFrom(prior)
        t=time.perf_counter_ns(); expected=full_advance(full);full_ms=(time.perf_counter_ns()-t)/1e6
        t=time.perf_counter_ns();actual=engine.advance(fast); fast_ms=(time.perf_counter_ns()-t)/1e6
        if expected.SerializeToString(deterministic=True)!=actual.lifecycle.SerializeToString(deterministic=True):
            raise AssertionError('P2X output differs from full P2W at '+str(idx))
        full_previous=expected.checkpoint
        fast_previous=actual.lifecycle.checkpoint
        full_times.append(full_ms);fast_times.append(fast_ms)
        step_stats.append({
            'windows':len(full.source_request.dynamic_request.windows),
            'full_ms':round(full_ms,3),'incremental_ms':round(fast_ms,3),
            'cached_p2t_windows':actual.reused_p2t_windows,
            'recomputed_p2t_windows':actual.recomputed_p2t_windows,
            'cached_temporal_windows':actual.reused_temporal_windows,
            'recomputed_temporal_windows':actual.recomputed_temporal_windows,
            'full_p2v_cache_hit':actual.reused_p2v_result,
            'cache_bytes':engine.cached_bytes,
            'result_exact_parity':True})
    return {'steps':step_stats,'full_total_ms':sum(full_times),
            'incremental_total_ms':sum(fast_times),
            'later_full_ms':sum(full_times[1:]),'later_incremental_ms':sum(fast_times[1:])}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',required=True)
    ap.add_argument('--rounds',type=int,default=5)
    args=ap.parse_args()
    if not 1<=args.rounds<=30:ap.error('rounds must be 1..30')
    # Source construction and first P2V computation are excluded from timed calls.
    sources=build_sources()
    rounds=[run(sources) for _ in range(args.rounds)]
    report={
        'milestone':'C15 T3 P2X', 'platform':platform.platform(),
        'python':sys.version.split()[0],
        'description':'isolated Linux CPU synthetic sliding-window benchmark; construction excluded',
        'rounds':args.rounds,'updates_per_round':len(sources),
        'first_round':rounds[0],
        'median_total_full_ms':round(statistics.median(x['full_total_ms'] for x in rounds),3),
        'median_total_incremental_ms':round(statistics.median(x['incremental_total_ms'] for x in rounds),3),
        'median_later_full_ms':round(statistics.median(x['later_full_ms'] for x in rounds),3),
        'median_later_incremental_ms':round(statistics.median(x['later_incremental_ms'] for x in rounds),3),
        'all_exact_parity':all(all(step['result_exact_parity'] for step in row['steps']) for row in rounds),
        'warnings':['synthetic only; not real-sensor validation',
                    'P2X HMAC receipts are process-local, not durable host attestations',
                    'upstream source_result generation is excluded from benchmark',
                    'full recomputation remains required after eviction, restart or cache miss',
                    'not measured on Windows; no real-device performance guarantee']}
    Path(args.out).parent.mkdir(parents=True,exist_ok=True)
    Path(args.out).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k.startswith('median') or k in ('rounds','updates_per_round','all_exact_parity')},indent=2))

if __name__=='__main__':main()
