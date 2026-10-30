"""Offline synthetic P2W CPU timing: full P2V verification versus state merge.

Usage: PYTHONPATH=. python tools/run_c15_t3_p2w_profile.py --out /tmp/p2w.json
The private _merge_preverified path is profiling-only; it does NOT validate inputs.
"""
import argparse
import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from cognitum.spatial_dynamic_scene_robustness import analyze as evaluate_p2v, verify as verify_p2v
from cognitum.spatial_map_lifecycle import advance, _merge_preverified, verify, checkpoint_digest
from cognitum.proto import spatial_map_lifecycle_pb2 as pb
from tests.test_c15_t3_p2v_dynamic_scene_robustness import fixture
from tests.test_c15_t3_p2u_dynamic_scene_mapping import shifted

def timing(action,n=30):
    for _ in range(3):action()
    results=[]
    for _ in range(n):
        t=time.perf_counter_ns();action();results.append((time.perf_counter_ns()-t)/1e6)
    return {'count':n,'median_ms':round(statistics.median(results),4),
            'min_ms':round(min(results),4),
            'p95_ms':round(sorted(results)[int(.95*(n-1))],4)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path);parser.add_argument('--iterations',type=int,default=30)
    args=parser.parse_args()
    if not 5 <= args.iterations <= 200: parser.error('iterations must be 5..200')
    first=fixture(); source=evaluate_p2v(first)
    req=pb.P2WUpdateRequest(schema_version=1,source_request=first,source_result=source,
         max_resident_cells=30,max_resident_objects=3,max_idle_ticks=1000,sequence=1,research_only=True)
    assert verify(req,advance(req))
    q=fixture();q.dynamic_request.windows.add().CopyFrom(shifted(q.dynamic_request.windows[0],200))
    second=evaluate_p2v(q)
    next_req=pb.P2WUpdateRequest(schema_version=1,source_request=q,source_result=second,
         previous=advance(req).checkpoint,max_resident_cells=8,max_resident_objects=1,
         max_idle_ticks=1000,sequence=2,research_only=True)
    assert verify(next_req,advance(next_req))
    p2v=timing(lambda:verify_p2v(q,second),args.iterations)
    merge=timing(lambda:_merge_preverified(next_req),args.iterations)
    end_to_end=timing(lambda:advance(next_req),args.iterations)
    tracemalloc.start()
    checkpoint=advance(next_req).checkpoint
    current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    result={'study':'C15-P2W-synthetic-local-cost-v1','mode':'Python CPU single-process offline',
            'hardware':{'platform':platform.platform(),'python':sys.version.split()[0],
                        'machine':platform.machine()},
            'source':{'captures':len(second.cameras),'cells':len(second.cells),'identities':len(second.identities)},
            'verified_p2v_ms':p2v,'preverified_merge_only_ms':merge,'public_advance_ms':end_to_end,
            'caution':'Preverified merge timing bypasses trust verification ONLY for profiling; public advance always verifies. Full P2V still replays all windows; not an end-to-end incremental P2V engine. Synthetic samples are not cross-platform performance benchmarks.',
            'checkpoint':{'sequence':checkpoint.sequence,'resident_cells':len(checkpoint.cells),
                          'active_static_evidence':len(checkpoint.current_stationary_hypothetical_volume.evidence),
                          'resident_objects':len(checkpoint.objects),'protobuf_bytes':checkpoint.ByteSize(),
                          'sha256':checkpoint.checkpoint_sha256.hex(),
                          'integrity_matches':checkpoint_digest(checkpoint)==checkpoint.checkpoint_sha256},
            'tracemalloc_peak_bytes_one_advance':peak}
    blob=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.out:args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(blob)
    print(blob)
if __name__=='__main__':main()
