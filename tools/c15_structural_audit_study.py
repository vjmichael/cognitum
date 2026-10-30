"""Independent seeded oracle for C15 T2/T3 research-only consistency audit.

Synthetic per-cell evidence is generated independently, then an oracle computes
aggregate outcomes without invoking the reference volumetric classifier.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, random
from cognitum.proto import spatial_composition_pb2 as s, spatial_volume_pb2 as v
from cognitum.proto import spatial_structural_audit_pb2 as a
from cognitum.spatial_structural_audit import audit


def one(seed: int):
    rng=random.Random(seed)
    graph=s.StructureGraph(schema_version=1,graph_id='test_assembly',conversation_id='trial',research_only=True)
    graph.nodes.add(node_id='object',kind='object',source_ref='model',evidence=s.EVIDENCE_INFERRED)
    grid=v.VolumeGrid(schema_version=1,volume_id='grid',conversation_id='trial',voxel_size_m=.1,max_axis=16,research_only=True)
    request=a.StructuralAuditRequest(schema_version=1,conversation_id='trial',graph_id='test_assembly',volume_id='grid',research_only=True)
    is_solid=rng.choice([True,False]);length=rng.randint(1,16)
    claim=request.claims.add(claim_id='region',node_id='object',source_ref='proposal',expected=a.SPATIAL_EXPECT_OCCUPIED if is_solid else a.SPATIAL_EXPECT_FREE)
    claim.box.min_x=0;claim.box.max_x=length-1
    support=contra=unres=conflict=pred_only=0
    cases=[]
    for x in range(length):
        label=rng.choice(['support','contradict','unknown','predicted','conflicted'])
        cases.append(label)
        target=v.VOLUME_MEASURED_OCCUPIED if is_solid else v.VOLUME_MEASURED_FREE
        other=v.VOLUME_MEASURED_FREE if is_solid else v.VOLUME_MEASURED_OCCUPIED
        if label=='support':grid.evidence.add(x=x,kind=target,source_id='sensor1',tick=1,reliability=.9);support+=1
        elif label=='contradict':grid.evidence.add(x=x,kind=other,source_id='sensor1',tick=1,reliability=.9);contra+=1
        elif label=='predicted':grid.evidence.add(x=x,kind=v.VOLUME_PREDICTED_OCCUPIED,source_id='model1',tick=1,reliability=.9);unres+=1;pred_only+=1
        elif label=='conflicted':
            grid.evidence.add(x=x,kind=target,source_id='sensor1',tick=1,reliability=.9)
            grid.evidence.add(x=x,kind=other,source_id='sensor2',tick=1,reliability=.9)
            conflict+=1
        else:unres+=1
    expected = (a.SPATIAL_AUDIT_MIXED if conflict or (support and contra) else
                a.SPATIAL_AUDIT_CONTRADICTED_BY_CLAIMED_EVIDENCE if contra else
                a.SPATIAL_AUDIT_CONSISTENT_WITH_CLAIMED_EVIDENCE if support and not unres else
                a.SPATIAL_AUDIT_INDETERMINATE)
    report=audit(graph,grid,request)
    got=report.audits[0]
    actual=(got.state,got.claimed_support_cells,got.claimed_contradiction_cells,
            got.unresolved_cells,got.conflicting_cells,got.predicted_only_cells,got.total_cells)
    oracle=(expected,support,contra,unres,conflict,pred_only,length)
    assert actual==oracle, f'{seed}: {actual} != {oracle}'
    assert not report.grants_authority and report.research_only
    return {'seed':seed,'status':a.SpatialAuditState.Name(expected),'cells':length,
            'oracle_sha256':hashlib.sha256(','.join(cases).encode()).hexdigest(),
            'result_sha256':hashlib.sha256(report.SerializeToString(deterministic=True)).hexdigest()}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--trials',type=int,default=600)
    args=parser.parse_args();assert 1<=args.trials<=1000
    results=[one(i+9000) for i in range(args.trials)]
    counts=dict(collections.Counter(x['status'] for x in results))
    out={'milestone':'C15 T2/T3 P2A structural/volumetric adversarial oracle',
         'generator':'independent seeded per-cell label oracle, NOT real sensor evidence',
         'num_seeded_trials':len(results),'status_counts':counts,
         'all_oracle_comparisons_passed':True,'physical_validation':False,
         'sensor_authentication':False,'action_authorized':False,
         'scenario_seed_range':[9000,9000+len(results)-1],
         'trial_results':results}
    with open(args.output,'w') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'cases':len(results),'status_counts':counts,'all_passed':True}))

if __name__=='__main__':main()
