"""Seeded temporal identity *single transition* experiment, no learned embeddings.

Reports candidate accuracy vs abstention independently. Does not use IDF1/HOTA
because there are no real annotated continuous sequences or validated detections.
"""
import argparse
import hashlib
import json
import random
import time
from collections import Counter
from pathlib import Path
from scipy.optimize import linear_sum_assignment
from cognitum import spatial_temporal_tracking as engine
from tests.test_c15_p2c_temporal_tracking import fixture,pairs

SCENARIOS=('velocity_cross','appearance_swap','indistinguishable_swap','long_occlusion','spoofed_descriptor')

def run(case,seed):
    rng=random.Random(20261028+seed)
    jitter=rng.uniform(-.1,.1)
    snap,r=fixture(descriptors=True)
    for d in r.detections:
        d.position_world_m.x+=jitter
    if case=='velocity_cross':
        truth={'da':'a','db':'b'}
    elif case in ('appearance_swap','indistinguishable_swap','spoofed_descriptor'):
        # A and B reverse physical positions, but the last two samples
        # are stationary; the anonymous detections reveal physical ID only
        # through the synthetic externally supplied descriptor.
        for tr in r.tracks:
            value=0 if tr.object_id=='a' else 10
            for sample in tr.samples:sample.position_world_m.x=value
        for obj in snap.objects:obj.position_m.x=0 if obj.object_id=='a' else 10
        r.scene_sha256=__import__('cognitum.spatial_identity_association',fromlist=['digest']).digest(snap)
        r.process_sigma_m_per_tick=5
        r.max_speed_m_per_tick=15
        r.descriptor_weight=20
        truth={'da':'a','db':'b'}
        if case=='indistinguishable_swap':
            for tr in r.tracks:tr.samples[-1].descriptor[:]=[1,0]
            for d in r.detections:d.descriptor[:]=[1,0]
        elif case=='spoofed_descriptor':
            # Spoof source feature: reversing descriptors can induce
            # confident but WRONG ranked identities. Not trusted ground truth.
            for d in r.detections:
                d.descriptor[:]=[0,1] if d.detection_id=='da' else [1,0]
    elif case=='long_occlusion':
        for d in r.detections:d.tick=6
        r.max_gap_ticks=6
        r.process_sigma_m_per_tick=1
        r.max_speed_m_per_tick=15
        truth={'da':'a','db':'b'}
    started=time.perf_counter_ns()
    result=engine.propose(snap,r)
    duration_us=(time.perf_counter_ns()-started)//1000
    assert engine.verify_proposal(snap,r,result)
    proposal=pairs(result)
    pids=[proposal[k] for k in sorted(proposal)]
    # Independent classic position-only, global bipartite minimum distance.
    last=[(o.object_id,o.position_m.x) for o in sorted(snap.objects,key=lambda x:x.object_id)]
    dets=sorted(r.detections,key=lambda x:x.detection_id)
    cost=[[abs(d.position_world_m.x-x) for _,x in last] for d in dets]
    rows,cols=linear_sum_assignment(cost)
    baseline={dets[i].detection_id:last[j][0] for i,j in zip(rows,cols)}
    return {'scenario':case,'seed':seed,'correct_temporal':sum(proposal.get(k)==v for k,v in truth.items()),
       'correct_position_baseline':sum(baseline.get(k)==v for k,v in truth.items()),
       'n_truth':len(truth),'abstained':result.decision==2,
       'decision':result.DESCRIPTOR.fields_by_name['decision'].enum_type.values_by_number[result.decision].name,
       'unmatched':sum(not v for v in proposal.values()),'elapsed_us':duration_us,
       'no_authority':not result.grants_authority,'proposal_hash':engine.prior.digest(result).hex()}

def study(seeds=40):
    cases=[run(s,i) for s in SCENARIOS for i in range(seeds)]
    summaries={}
    for s in SCENARIOS:
        rows=[x for x in cases if x['scenario']==s]
        summaries[s]={'trials':len(rows),'temporal_top1_correct':sum(x['correct_temporal'] for x in rows),
          'position_hungarian_correct':sum(x['correct_position_baseline'] for x in rows),
          'total_truth':sum(x['n_truth'] for x in rows),
          'ambiguous':sum(x['abstained'] for x in rows),
          'unmatched':sum(x['unmatched'] for x in rows),
          'median_elapsed_microseconds':sorted(x['elapsed_us'] for x in rows)[len(rows)//2],
          'authority_grants':sum(not x['no_authority'] for x in rows)}
    assert all(x['no_authority'] for x in cases)
    return {'milestone':'C15_T1_P2C','study':'synthetic_single_transition_identity_tracking',
        'ground_truth_is_held_out_from_tracker':True,
        'embedding':'handcrafted 2D vectors, NOT a trained visual re-identification model',
        'baselines':['P2C constant velocity plus synthetic descriptor','SciPy Hungarian last-position assignment'],
        'limitations':['no real images/sensors','untrusted descriptors may be spoofed','no calibrated posterior or HOTA/IDF1',
             'abstention is not correct identity recovery','single transition, not full multi-frame tracker'],
        'summary':summaries,'cases':cases}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path);args=parser.parse_args()
    record=study();raw=json.dumps(record,sort_keys=True,indent=2)+'\n'
    if args.out:args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(raw)
    print(json.dumps({'summary':record['summary'],'sha256':hashlib.sha256(raw.encode()).hexdigest()},indent=2,sort_keys=True))
if __name__=='__main__':main()
