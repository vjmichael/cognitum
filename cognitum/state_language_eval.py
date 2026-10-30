"""Reproducible P8 human-authored synthetic *utterance*, not model, evaluation.

Frozen JSONL gold labels are independent of reducer outputs but authored by a
single engineer. No claim of naturally sampled transcripts, human inter-rater
agreement, live Lu, LLM extraction, or production confidence calibration.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import perf_counter_ns

from cognitum.proto import interpretation_pb2 as p
from cognitum.state_language import interpret, interpret_frame

ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/'evals/c07_p8_conversational_cases.jsonl'
GOLD_SHA256='540834d870aa15451391dc292a2391a66723b194bfe2a71a98fcfe06ec86b2ec'
LABELS={p.UtteranceClass.Name(x) for x in (
    p.NO_STATE_CHANGE,p.TENTATIVE_PLAN,p.DECISION_CANDIDATE,
    p.CHANGE_OF_MIND_CANDIDATE,p.CORRECTION_CANDIDATE,
    p.RETRACTION_CANDIDATE,p.ABSTAIN_UNRESOLVED)}


def cases():
    raw=CORPUS.read_bytes()
    if sha256(raw).hexdigest()!=GOLD_SHA256:
        raise ValueError('gold labels changed; require explicit new corpus version')
    data=[json.loads(line) for line in raw.splitlines()]
    if len(data)!=131 or len({x['id'] for x in data})!=len(data):
        raise ValueError('unexpected case count / duplicate ids')
    if Counter(x['split'] for x in data) != {'development':95,'holdout':36}:
        raise ValueError('unexpected evaluation split')
    if any(x['label'] not in LABELS for x in data):
        raise ValueError('unknown annotation label')
    return data


def turn_for(c):
    return p.ConversationTurn(schema_version=1,scope_id='c07_p8',
        source_session_id='chat_'+c['split'],source_entry_id=str(int(c['id'].split('-')[1])),
        speaker_role=c['speaker_role'],utterance=c['utterance'],
        prior_decision=c['prior_decision'])


def naive_latest(c):
    return ('DECISION_CANDIDATE' if c['speaker_role']=='user' else 'NO_STATE_CHANGE')


def keyword_baseline(c):
    if c['speaker_role'] != 'user':return 'NO_STATE_CHANGE'
    u=c['utterance'].lower()
    if 'maybe' in u or 'might' in u or 'could' in u: return 'TENTATIVE_PLAN'
    if 'i meant' in u or 'correction:' in u:return 'CORRECTION_CANDIDATE'
    if 'changed my mind' in u or 'actually' in u:return 'CHANGE_OF_MIND_CANDIDATE'
    if 'cancel ' in u or 'withdraw ' in u:return 'RETRACTION_CANDIDATE'
    return 'DECISION_CANDIDATE'


def score(cases, predicted):
    total=len(cases)
    correct=sum(g['label']==q for g,q in zip(cases,predicted))
    confusion=Counter((g['label'],q) for g,q in zip(cases,predicted))
    classes=sorted(LABELS)
    stats={}
    for label in classes:
        tp=confusion[(label,label)]
        fp=sum(confusion[(other,label)] for other in classes if other!=label)
        fn=sum(confusion[(label,other)] for other in classes if other!=label)
        prec=tp/(tp+fp) if tp+fp else 0.0
        rec=tp/(tp+fn) if tp+fn else 0.0
        stats[label]={'gold':sum(c['label']==label for c in cases),
                      'predicted':sum(q==label for q in predicted),
                      'precision':round(prec,4),'recall':round(rec,4),
                      'f1':round(2*prec*rec/(prec+rec),4) if prec+rec else 0.0}
    dangerous={'NO_STATE_CHANGE','TENTATIVE_PLAN','ABSTAIN_UNRESOLVED'}
    update_labels={'DECISION_CANDIDATE','CHANGE_OF_MIND_CANDIDATE',
                   'CORRECTION_CANDIDATE','RETRACTION_CANDIDATE'}
    return {
        'cases':total,'correct':correct,'accuracy':round(correct/total,4),
        'macro_f1':round(sum(v['f1'] for v in stats.values())/len(stats),4),
        'false_committed_decisions':sum(g['label'] in dangerous and q=='DECISION_CANDIDATE'
                                       for g,q in zip(cases,predicted)),
        'false_action_proposals':sum(g['label'] in dangerous and q in update_labels
                                     for g,q in zip(cases,predicted)),
        'missed_action_candidates':sum(g['label'] in update_labels and q not in update_labels
                                        for g,q in zip(cases,predicted)),
        'abstentions':predicted.count('ABSTAIN_UNRESOLVED'),
        'per_class':stats,
        'errors':[{'id':g['id'],'gold':g['label'],'predicted':q,'utterance':g['utterance']}
                  for g,q in zip(cases,predicted) if q!=g['label']],
    }


def evaluate():
    allcases=cases()
    output={'tier':'single_author_synthetic_utterances_no_LLM_or_Lu',
            'gold_sha256':GOLD_SHA256,'safety':'candidate-only; no StateEvent writes',
            'splits':{}}
    for split in ('development','holdout'):
        subset=[c for c in allcases if c['split']==split]
        begin=[];pred=[]
        for c in subset:
            input_frame=turn_for(c).SerializeToString(deterministic=True)
            before=perf_counter_ns()
            result=p.InterpretationProposal.FromString(interpret_frame(input_frame))
            begin.append((perf_counter_ns()-before)/1e6)
            if result.may_write_state_directly or not result.requires_host_review:
                raise AssertionError('unsafe interpreter output')
            if result.candidate_span and result.candidate_span not in c['utterance']:
                raise AssertionError('generated candidate not exact source substring')
            pred.append(p.UtteranceClass.Name(result.label))
        output['splits'][split]={
            'C07_lexical_reference':score(subset,pred),
            'naive_latest_user_turn':score(subset,[naive_latest(c) for c in subset]),
            'keyword_baseline':score(subset,[keyword_baseline(c) for c in subset]),
            'reference_median_ms_per_turn':round(median(begin),4),
        }
    return output


if __name__=='__main__':
    print(json.dumps(evaluate(),indent=2,sort_keys=True))
