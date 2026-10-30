"""C07 P6: deterministic, *offline synthetic* historical-query evaluation.

Only hand-labelled scenario expectations count as an oracle. Baselines deliberately
implement less than C07; they are not security-equivalent alternatives. This
module does not create grants, authenticate sources, or execute a language model.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Callable

from cognitum.proto import state_pb2 as pb
from cognitum.state_revision import StateLedger
from cognitum.state_temporal import project_as_of

SCOPE = 'c07p6'


@dataclass(frozen=True)
class Expected:
    claim_id: str
    value: str
    status: int = pb.ACTIVE
    origin: int = pb.USER_VERIFIED
    uncertainty: int = pb.UNCERTAINTY_UNSPECIFIED


@dataclass(frozen=True)
class Case:
    name: str
    valid_at: int
    known_at: int
    claims: tuple[Expected, ...]
    conflicts: tuple[tuple[str, str], ...] = ()
    include_inactive: bool = False


@dataclass(frozen=True)
class Scenario:
    name: str
    events: tuple[pb.StateEvent, ...]
    cases: tuple[Case, ...]


def source_for(tag: str) -> pb.SourceEvidence:
    # A fixture identity and synthetic digest. NOT a real canonical ANSF attestation.
    return pb.SourceEvidence(session_id='synthetic_' + tag.split('_')[0],
        root_entry_id='1', revision_entry_id='1',
        content_sha256=sha256(tag.encode('utf-8')).hexdigest(),snapshot_id='snap0')


def event(group: str, n: int, *, claim: str = 'main', value: str = 'draft',
          action: int = pb.ASSERT, at: int = 1000, effective: int | None = None,
          end: int = 0, origin: int = pb.USER_VERIFIED,
          uncertainty: int = pb.UNCERTAINTY_UNSPECIFIED, note: str = '',
          corrects: str = '', subject: str | None = None) -> pb.StateEvent:
    event_id = f'{group}_e{n}' if claim == 'main' else f'{group}_{claim}_e{n}'
    return pb.StateEvent(schema_version=1, event_id=event_id,scope_id=SCOPE,
        claim_id=f'{group}_{claim}',subject_id=subject or f'{group}_subject',
        predicate='current_plan',value_kind=pb.TEXT,value_text=value,
        origin=origin,action=action,expected_revision=n-1 if claim=='main' else 0,
        recorded_at_ms=at,effective_at_ms=effective if effective is not None else at,
        valid_until_ms=end, uncertainty_kind=uncertainty,uncertainty_note=note,
        corrects_event_id=corrects,source=source_for(event_id))


def c(name: str, valid: int, known: int, *values: Expected,
      conflicts: tuple[tuple[str,str], ...] = (), inactive: bool = False) -> Case:
    return Case(name,valid,known,tuple(values),conflicts,inactive)


def x(group: str, value: str, *, claim='main', status=pb.ACTIVE,
      origin=pb.USER_VERIFIED, uncertainty=pb.UNCERTAINTY_UNSPECIFIED) -> Expected:
    return Expected(f'{group}_{claim}',value,status,origin,uncertainty)


def golden_scenarios() -> tuple[Scenario, ...]:
    """Explicit human-authored answer keys: never computed from the reducer."""
    g='switch'
    switch=Scenario(g,(event(g,1),event(g,2,value='final',action=pb.SUPERSEDE,at=2000)),(
        c('before assertion',900,3000),
        c('old value historically',1500,3000,x(g,'draft')),
        c('old knowledge cutoff',2500,1500,x(g,'draft')),
        c('new value at boundary',2000,3000,x(g,'final')),
        c('new value after',3000,3000,x(g,'final')),
        c('not yet recorded',2500,999),
    ))
    g='retro'
    retro=Scenario(g,(
        event(g,1,value='initial'),
        event(g,2,value='revised',action=pb.SUPERSEDE,at=3000),
        event(g,3,value='revised',action=pb.TEMPORAL_CORRECT,at=3500,effective=800,corrects='retro_e2'),
    ),(
        c('correction not yet known',900,3400),
        c('correction now known',900,3500,x(g,'revised')),
        c('before correction historical',1500,3400,x(g,'initial')),
        c('after correction historical',1500,3500,x(g,'revised')),
        c('recent',3200,3500,x(g,'revised')),
    ))
    g='bounded'
    bounded=Scenario(g,(event(g,1,value='leased',end=1600),
        event(g,2,value='renewed',action=pb.SUPERSEDE,at=2000)),(
        c('start boundary',1000,3000,x(g,'leased')),
        c('end exclusive below',1599,3000,x(g,'leased')),
        c('end exclusive exact',1600,3000),
        c('gap',1700,3000),
        c('new segment',2000,3000,x(g,'renewed')),
        c('gap include inactive',1700,3000,x(g,'leased',status=pb.EXPIRED),inactive=True),
    ))
    g='challenge'
    challenge=Scenario(g,(event(g,1,value='proposed'),
        event(g,2,value='proposed',action=pb.CHALLENGE,at=2000,origin=pb.MODEL_HYPOTHESIS),
        event(g,3,value='proposed',action=pb.CONFIRM,at=3000)),(
        c('pre challenge',1500,4000,x(g,'proposed')),
        c('challenge known but not yet effective',1500,2500,x(g,'proposed')),
        c('challenge effective',2500,4000,x(g,'proposed',status=pb.DISPUTED)),
        c('confirmed',3500,4000,x(g,'proposed')),
    ))
    g='retract'
    retract=Scenario(g,(event(g,1,value='withdrawn'),
        event(g,2,value='withdrawn',action=pb.RETRACT,at=2000)),(
        c('prior',1500,3000,x(g,'withdrawn')),
        c('hidden terminal',2500,3000),
        c('historical terminal marker',2500,3000,x(g,'withdrawn',status=pb.RETRACTED),inactive=True),
        c('prior known',2500,1500,x(g,'withdrawn')),
    ))
    g='conflict'
    left=event(g,1,claim='left',value='east',end=1800)
    right=event(g,1,claim='right',value='west',at=1500,end=2200)
    conflict=Scenario(g,(left,right),(
        c('only left',1400,3000,x(g,'east',claim='left')),
        c('overlap',1600,3000,x(g,'east',claim='left'),x(g,'west',claim='right'),
          conflicts=(('conflict_left','conflict_right'),)),
        c('overlap begins',1500,3000,x(g,'east',claim='left'),x(g,'west',claim='right'),
          conflicts=(('conflict_left','conflict_right'),)),
        c('overlap ends just before exclusive bound',1799,3000,
          x(g,'east',claim='left'),x(g,'west',claim='right'),
          conflicts=(('conflict_left','conflict_right'),)),
        c('both observed as of overlap',1600,1600,
          x(g,'east',claim='left'),x(g,'west',claim='right'),
          conflicts=(('conflict_left','conflict_right'),)),
        c('after left end',1800,3000,x(g,'west',claim='right')),
        c('after both ends',2200,3000),
        c('right not yet known',1600,1499,x(g,'east',claim='left')),
    ))
    g='delayed'
    delayed=Scenario(g,(event(g,1,value='evidence arrived',at=3000,effective=1200),),(
        c('valid before record',1400,2999),
        c('valid after record',1400,3000,x(g,'evidence arrived')),
        c('before effective',1100,4000),
        c('future effective',3500,4000,x(g,'evidence arrived')),
    ))
    g='uncertain'
    uncertain=Scenario(g,(event(g,1,value='candidate',origin=pb.MODEL_HYPOTHESIS,
        uncertainty=pb.OPEN_QUESTION,note='Unconfirmed in a synthetic fixture.'),
        event(g,2,value='candidate',action=pb.CONFIRM,at=2000)),(
        c('pre confirmation',1500,4000,x(g,'candidate',origin=pb.MODEL_HYPOTHESIS,
          uncertainty=pb.OPEN_QUESTION)),
        c('post confirmation',2500,4000,x(g,'candidate',uncertainty=pb.OPEN_QUESTION)),
        c('unknown confirmation',2500,1500,x(g,'candidate',origin=pb.MODEL_HYPOTHESIS,
          uncertainty=pb.OPEN_QUESTION)),
    ))
    g='interval'
    interval=Scenario(g,(event(g,1,value='temporary',end=3000),
        event(g,2,value='temporary',action=pb.TEMPORAL_CORRECT,
              at=4000,effective=1000,end=1500,corrects='interval_e1')),( 
        c('prior end known',2000,3500,x(g,'temporary')),
        c('end revised',2000,4000),
        c('still inside corrected interval',1400,4000,x(g,'temporary')),
        c('at revised cutoff',1500,4000),
    ))
    return switch,retro,bounded,challenge,retract,conflict,delayed,uncertain,interval


def corpus_sha256(scenarios: tuple[Scenario,...] | None = None) -> str:
    """Fingerprint labelled inputs AND human-written oracle; pins dataset version."""
    scenarios = golden_scenarios() if scenarios is None else scenarios
    items=[]
    for scenario in scenarios:
        items.append({
            'name':scenario.name,
            'events':[e.SerializeToString(deterministic=True).hex() for e in scenario.events],
            'cases':[{'name':case.name,'valid':case.valid_at,'known':case.known_at,
                      'include_inactive':case.include_inactive,
                      'claims':[(c.claim_id,c.value,c.status,c.origin,c.uncertainty)
                                for c in case.claims],
                      'conflicts':case.conflicts} for case in scenario.cases]
        })
    payload=json.dumps(items,sort_keys=True,separators=(',',':')).encode('utf-8')
    return sha256(payload).hexdigest()


def query(case: Case) -> pb.AsOfQuery:
    return pb.AsOfQuery(schema_version=1,scope_id=SCOPE,valid_at_ms=case.valid_at,
        known_at_ms=case.known_at,include_inactive=case.include_inactive)


def observed(frame: pb.HistoricalProjection) -> tuple[tuple[Expected, ...],tuple[tuple[str,str], ...]]:
    claims=tuple(sorted((Expected(v.claim_id,v.value_text,v.status,v.origin,v.uncertainty_kind)
                         for v in frame.claims),key=lambda v:v.claim_id))
    conflicts=tuple(sorted(tuple(sorted((p.first_claim_id,p.second_claim_id)))
                           for p in frame.conflicts))
    return claims,conflicts


def expected(case: Case):
    return tuple(sorted(case.claims,key=lambda v:v.claim_id)),tuple(sorted(
        tuple(sorted(edge)) for edge in case.conflicts))


def chronological_register(events: tuple[pb.StateEvent, ...], case: Case):
    """One-clock register. Honors recording cutoff; ignores valid-time and conflicts."""
    state: dict[str,Expected] = {}
    for evt in events:
        if evt.recorded_at_ms > case.known_at:
            continue
        old=state.get(evt.claim_id)
        if evt.action in (pb.ASSERT,pb.SUPERSEDE):
            state[evt.claim_id]=Expected(evt.claim_id,evt.value_text,pb.ACTIVE,evt.origin,evt.uncertainty_kind)
        elif old is not None and evt.action == pb.CHALLENGE:
            state[evt.claim_id]=Expected(old.claim_id,old.value,pb.DISPUTED,old.origin,old.uncertainty)
        elif old is not None and evt.action == pb.CONFIRM:
            state[evt.claim_id]=Expected(old.claim_id,old.value,pb.ACTIVE,max(old.origin,evt.origin),old.uncertainty)
        elif old is not None and evt.action in (pb.RETRACT,pb.EXPIRE):
            state[evt.claim_id]=Expected(old.claim_id,old.value,pb.RETRACTED if evt.action==pb.RETRACT else pb.EXPIRED,
                                         old.origin,old.uncertainty)
        # Ordinary chronological register has no temporal-correction operation.
    return tuple(sorted((x for x in state.values() if case.include_inactive or
                       x.status not in (pb.RETRACTED,pb.EXPIRED)),key=lambda v:v.claim_id)),()


def effective_clock_register(events: tuple[pb.StateEvent, ...], case: Case):
    """One-clock valid-time register. Omits knowledge cutoff and history corrections."""
    state: dict[str,Expected] = {}
    for evt in events:
        if evt.effective_at_ms > case.valid_at:
            continue
        old=state.get(evt.claim_id)
        if evt.action in (pb.ASSERT,pb.SUPERSEDE):
            state[evt.claim_id]=Expected(evt.claim_id,evt.value_text,pb.ACTIVE,evt.origin,evt.uncertainty_kind)
        elif old is not None and evt.action == pb.CHALLENGE:
            state[evt.claim_id]=Expected(old.claim_id,old.value,pb.DISPUTED,old.origin,old.uncertainty)
        elif old is not None and evt.action == pb.CONFIRM:
            state[evt.claim_id]=Expected(old.claim_id,old.value,pb.ACTIVE,max(old.origin,evt.origin),old.uncertainty)
        elif old is not None and evt.action in (pb.RETRACT,pb.EXPIRE):
            state[evt.claim_id]=Expected(old.claim_id,old.value,pb.RETRACTED if evt.action==pb.RETRACT else pb.EXPIRED,
                                         old.origin,old.uncertainty)
    return tuple(sorted((x for x in state.values() if case.include_inactive or
                       x.status not in (pb.RETRACTED,pb.EXPIRED)),key=lambda v:v.claim_id)),()


def evaluate() -> dict:
    scenarios=golden_scenarios()
    systems: dict[str,Callable]= {'chronological_register':chronological_register,
                                  'effective_clock_register':effective_clock_register}
    tallies={n:{'case_count':0,'value_status_correct':0,'full_provenance_uncertainty_correct':0,
                'conflict_correct':0,'exact_case_correct':0,'incorrect_or_extra_claims':0,'missed_claims':0,
                'gold_conflict_positive_cases':0,'detected_conflict_positive_cases':0,
                'false_conflict_positive_cases':0}
             for n in (*systems,'C07_bitemporal')}
    cases_total=0
    divergent=[]
    for scenario in scenarios:
        ledger=StateLedger(SCOPE)
        ledger.apply_batch(scenario.events)
        for case in scenario.cases:
            cases_total+=1
            oracle_claims,oracle_conflicts=expected(case)
            obs={'C07_bitemporal':observed(project_as_of(ledger,query(case)))}
            obs.update({key:impl(scenario.events,case) for key,impl in systems.items()})
            for name,(claims,edges) in obs.items():
                record=tallies[name]
                record['case_count']+=1
                simplified=lambda xs:tuple((a.claim_id,a.value,a.status) for a in xs)
                vs=simplified(claims)==simplified(oracle_claims)
                prov=claims==oracle_claims
                ce=edges==oracle_conflicts
                record['value_status_correct']+=vs
                record['full_provenance_uncertainty_correct']+=prov
                record['conflict_correct']+=ce
                record['gold_conflict_positive_cases']+=bool(oracle_conflicts)
                record['detected_conflict_positive_cases']+=bool(oracle_conflicts) and bool(edges)
                record['false_conflict_positive_cases']+=bool(edges) and not bool(oracle_conflicts)
                record['exact_case_correct']+=prov and ce
                record['incorrect_or_extra_claims']+=len(set(simplified(claims))-set(simplified(oracle_claims)))
                record['missed_claims']+=len(set(simplified(oracle_claims))-set(simplified(claims)))
            if obs['C07_bitemporal']!=(oracle_claims,oracle_conflicts):
                divergent.append(f'{scenario.name}/{case.name}')
    return {'evaluation_tier':'hand_labeled_synthetic_no_model',
            'Lu_or_model_executed':False,'scenario_count':len(scenarios),
            'golden_query_count':cases_total,'golden_corpus_sha256':corpus_sha256(scenarios),'input_event_count':sum(len(x.events) for x in scenarios),
            'results':tallies,'C07_oracle_mismatches':divergent,
            'baseline_capabilities':{
                'chronological_register':['recorded-time cutoff','simple claim status changes'],
                'effective_clock_register':['valid-time cutoff','simple claim status changes'],
                'C07_bitemporal':['both clocks','intervals','temporal correction','conflict edges',
                    'provenance qualifiers','bounded source-fenced SQLite replay separately tested']},
            'warnings':['Baseline registers omit canonical host authorization, durable replay and/or a temporal clock.',
                        'Hand-labeled synthetic fixtures are not representative of live language-model accuracy.',
                        'Provenance labels here are synthetic event metadata, not verified Lu user claims.']}
