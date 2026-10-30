"""Reproducible offline C15/P2B acceptance study (synthetic IDs are oracle-only).

No cameras, ML models, host authorization, or real-world tracking.
"""
import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from cognitum.proto import spatial_identity_pb2 as pb
from cognitum.proto import spatial_scene_pb2 as sp
from cognitum import spatial_identity_association as engine
from tests.test_c15_p2b_identity_association import observed,seed,request

SCENARIOS=('stable_same_class','position_swap','near_tie','distinct_categories','source_mismatch','occlusion')


def trial(scenario, seed_number):
    rng=random.Random(440000 + seed_number)
    shift=rng.uniform(-100,100)
    if scenario == 'distinct_categories':
        state=seed([observed('a',shift,category='drone'), observed('b',shift+10,category='person')])
        obs=[('oa',shift+rng.uniform(-.1,.1),'sensor_a','drone',2),
             ('ob',shift+10+rng.uniform(-.1,.1),'sensor_a','person',2)]
        expected={'oa':'a','ob':'b'}
    else:
        state=seed([observed('a',shift),observed('b',shift+10)])
        if scenario=='stable_same_class' or scenario=='occlusion':
            obs=[('oa',shift+rng.uniform(-.1,.1)),('ob',shift+10+rng.uniform(-.1,.1))]
            expected={'oa':'a','ob':'b'}
        elif scenario=='position_swap':
            # True physical objects swap places, with no appearance cues.
            obs=[('oa',shift+10+rng.uniform(-.1,.1)),('ob',shift+rng.uniform(-.1,.1))]
            expected={'oa':'a','ob':'b'}
        elif scenario=='near_tie':
            obs=[('oa',shift+5)]
            expected={'oa':'a'}  # arbitrary latent ground truth, not observable
        elif scenario=='source_mismatch':
            obs=[('oa',shift,'sensor_b','drone',2),('ob',shift+10,'sensor_b','drone',2)]
            expected={'oa':'a','ob':'b'}
    if scenario=='occlusion':
        cmd=sp.SceneCommand(schema_version=1,scene_id=state.scene_id,
              conversation_id=state.conversation_id,task_id='task_x',trace_id='trace_x',
              request_id='occlude_seed',expected_scene_revision=state.revision)
        cmd.mutations.add(kind=sp.MUTATION_OCCLUDE,object_id='a',tick=2,expected_object_version=1)
        state,_=__import__('cognitum.spatial_scene_reference',fromlist=['apply']).apply(
            state,cmd,admit=lambda *x:True)
        obs=[tuple([*o,'sensor_a','drone',3]) if len(o)==2 else o for o in obs]
    r=request(state,obs,speed=20,sigma=(3.0 if scenario=='near_tie' else .7),cost=9,k=4)
    out=engine.propose(state,r)
    assert engine.verify_proposal(state,r,out)
    assert out.research_only and not out.grants_authority
    proposal={a.observation_id:a.object_id for a in out.hypotheses[0].pairs}
    correct=sum(proposal[k]==v for k,v in expected.items())
    return {
        'decision':pb.AssociationDecision.Name(out.decision),
        'identity_correct':correct,
        'identity_total':len(expected),
        'unmatched':sum(not x for x in proposal.values()),
        'scene_hash':engine.digest(state).hex(),
        'proposal_hash':engine.digest(out).hex(),
        'warnings':list(out.warnings),
        'authority_granted':out.grants_authority,
    }


def study():
    results=[]
    for scenario in SCENARIOS:
        for i in range(20):
            results.append({'scenario':scenario,'trial_seed':i,**trial(scenario,i)})
    summary={}
    for scenario in SCENARIOS:
        rows=[r for r in results if r['scenario']==scenario]
        summary[scenario]={'trials':len(rows),
            'decisions':dict(Counter(x['decision'] for x in rows)),
            'top_1_identity_correct':sum(x['identity_correct'] for x in rows),
            'identity_total':sum(x['identity_total'] for x in rows),
            'authority_grants':sum(x['authority_granted'] for x in rows)}
    assert sum(x['trials'] for x in summary.values())==120
    assert all(x['authority_grants']==0 for x in summary.values())
    assert summary['position_swap']['decisions']=={'ASSOCIATION_AMBIGUOUS':20}
    assert summary['near_tie']['decisions']=={'ASSOCIATION_AMBIGUOUS':20}
    assert summary['distinct_categories']['decisions']=={'ASSOCIATION_CANDIDATE_ONLY':20}
    assert summary['source_mismatch']['decisions']=={'ASSOCIATION_NO_COMPATIBLE_MATCH':20}
    return {'milestone':'C15_T1_P2B','status':'synthetic_research_only',
        'generator':'Python random.Random seeded 440000 + trial_seed; no model or sensor',
        'scenarios':summary,'trials':results,
        'interpretation':'top1 numerical rank is not authenticated object identity; ambiguous outcomes deliberately preserve abstention'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path);args=parser.parse_args()
    result=study();raw=json.dumps(result,sort_keys=True,indent=2)+'\n'
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(raw)
    print(json.dumps({'datasets':len(result['trials']),'scenarios':result['scenarios'],
        'evidence_sha256':hashlib.sha256(raw.encode()).hexdigest()},sort_keys=True,indent=2))

if __name__=='__main__':main()
