"""C07/P7 multi-conversation *synthetic*, hand-annotated historical evaluation.

The reference corpus deliberately interleaves unrelated source-backed entries
from multiple synthetic conversations. The independent labels apply ONLY to
one specified subject/predicate per query, not to the entire projection. Full
host-fenced publication still verifies all sources; these diagnostic target
filters are never a Lu-facing access-control or search operation.

All expected values/conflicts are authored in the case tables below. They are
NOT inferred from C07, its timestamps, or the comparison baselines.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from cognitum.proto import state_pb2 as pb
from cognitum.state_revision import StateLedger
from cognitum.state_temporal import project_as_of
from cognitum.state_evaluation import Expected, Case, chronological_register, effective_clock_register

SCOPE = 'c07p7'
PREDICATE = 'target_decision'

@dataclass(frozen=True)
class LongCase:
    name: str
    valid_at_ms: int
    known_at_ms: int
    values: tuple[Expected, ...]
    conflicts: tuple[tuple[str,str], ...] = ()

@dataclass(frozen=True)
class LongScenario:
    name: str
    subject_id: str
    events: tuple[pb.StateEvent, ...]
    cases: tuple[LongCase, ...]


def _e(group: str, claim: str, sequence: int, *, session: str, action: int,
       value: str, recorded: int, effective: int | None = None,
       origin: int = pb.USER_VERIFIED, until: int = 0,
       uncertainty: int = pb.UNCERTAINTY_UNSPECIFIED,
       note: str = '', corrects: str = '', predicate: str = PREDICATE,
       subject: str | None = None) -> pb.StateEvent:
    eid=f'{group}_{claim}_{sequence:02}'
    digest=sha256(f'{session}/{eid}/original-source'.encode()).hexdigest()
    # Stable, synthetic positive ANSF-like row ID, unique within a session.
    source_row=str(int.from_bytes(sha256(f'{session}/{eid}/row'.encode()).digest()[:8], 'big') % (2**55)+1)
    return pb.StateEvent(schema_version=1,event_id=eid,scope_id=SCOPE,
        claim_id=f'{group}_{claim}', subject_id=subject or f'{group}_subject',
        predicate=predicate,value_kind=pb.TEXT,value_text=value,origin=origin,
        action=action,expected_revision=sequence-1,
        recorded_at_ms=recorded,effective_at_ms=recorded if effective is None else effective,
        valid_until_ms=until,uncertainty_kind=uncertainty,uncertainty_note=note,
        corrects_event_id=corrects,
        source=pb.SourceEvidence(session_id=session,root_entry_id=source_row,
            revision_entry_id=source_row,content_sha256=digest,snapshot_id='snap_p7'))


def _background(group: str) -> tuple[pb.StateEvent, ...]:
    """24 unrelated memory events across six conversations; no target oracle shortcuts."""
    noise=[]
    for i in range(12):
        claim=f'noise{i:02}'
        chat=f'chat_{i%6}'
        start=1050+i*260
        noise.append(_e(group,claim,1,session=chat,action=pb.ASSERT,
            value=f'baseline_{i}',recorded=start,predicate='background_setting',
            subject=f'background_{i}'))
        noise.append(_e(group,claim,2,session=f'chat_{(i+2)%6}',
            action=pb.SUPERSEDE,value=f'updated_{i}',recorded=start+3500,
            predicate='background_setting',subject=f'background_{i}'))
    return tuple(noise)


def _label(group: str, value: str, claim: str='main', *,
           status: int=pb.ACTIVE, origin: int=pb.USER_VERIFIED,
           uncertainty: int=pb.UNCERTAINTY_UNSPECIFIED) -> Expected:
    return Expected(f'{group}_{claim}',value,status,origin,uncertainty)


def _case(name: str, valid: int, known: int, *values: Expected,
          conflicts: tuple[tuple[str,str],...]=()) -> LongCase:
    return LongCase(name,valid,known,tuple(values),conflicts)


def _finish(group: str, target: tuple[pb.StateEvent,...],
            cases: tuple[LongCase,...]) -> LongScenario:
    # Natural recording order, source events spanning six simulated chats.
    events=tuple(sorted(target+_background(group),key=lambda e:(e.recorded_at_ms,e.event_id)))
    return LongScenario(group,f'{group}_subject',events,cases)


def long_scenarios() -> tuple[LongScenario,...]:
    """Independent, manually authored target expectations for four timelines."""
    g='goals'; a=_label(g,'June'); b=_label(g,'July');
    disputed=_label(g,'July',status=pb.DISPUTED)
    h=_label(g,'August maybe','alternative',origin=pb.MODEL_HYPOTHESIS,
             uncertainty=pb.OPEN_QUESTION)
    overlap=((f'{g}_alternative',f'{g}_main'),)
    goals=_finish(g,(
        _e(g,'main',1,session='chat_0',action=pb.ASSERT,value='June',recorded=1000),
        _e(g,'main',2,session='chat_1',action=pb.SUPERSEDE,value='July',recorded=2000),
        _e(g,'main',3,session='chat_2',action=pb.CHALLENGE,value='July',
           origin=pb.MODEL_HYPOTHESIS,recorded=2500),
        _e(g,'alternative',1,session='chat_2',action=pb.ASSERT,
           value='August maybe',recorded=2600,origin=pb.MODEL_HYPOTHESIS,
           uncertainty=pb.OPEN_QUESTION,note='Model proposal; user has not confirmed.'),
        _e(g,'main',4,session='chat_1',action=pb.CONFIRM,value='July',recorded=3000),
        _e(g,'alternative',2,session='chat_3',action=pb.RETRACT,
           value='August maybe',recorded=3500,origin=pb.MODEL_HYPOTHESIS),
        _e(g,'main',5,session='chat_4',action=pb.SUPERSEDE,value='September',recorded=4000),
    ),(
        _case('not recorded',900,5000),_case('initial boundary',1000,5000,a),
        _case('before shift',1999,5000,a),_case('shift boundary',2000,5000,b),
        _case('before challenge',2499,5000,b),_case('challenge active',2500,5000,disputed),
        _case('model uncertainty overlaps',2600,5000,disputed,h,conflicts=overlap),
        _case('still disputed',2999,5000,disputed,h,conflicts=overlap),
        _case('verified but conflicting',3000,5000,b,h,conflicts=overlap),
        _case('model alternative withdrawn',3500,5000,b),
        _case('new user decision',4000,5000,_label(g,'September')),
        _case('recording cutoff initial',4500,1900,a),
        _case('recording cutoff challenge',4500,2800,disputed,h,conflicts=overlap),
        _case('recording cutoff confirmed',4500,3200,b,h,conflicts=overlap),
        _case('recording cutoff withdrawal',4500,3500,b),
        _case('recording cutoff before final',4500,3999,b),
        _case('recording cutoff final',4500,4000,_label(g,'September')),
    ))

    g='deadline'; old=_label(g,'January'); other=_label(g,'February','rival')
    extra=_label(g,'March maybe','hypothesis',origin=pb.MODEL_HYPOTHESIS,
                 uncertainty=pb.CONDITIONAL)
    conflict=((f'{g}_main',f'{g}_rival'),)
    second=((f'{g}_hypothesis',f'{g}_main'),)
    deadline=_finish(g,(
        _e(g,'main',1,session='chat_0',action=pb.ASSERT,value='January',recorded=1000),
        _e(g,'rival',1,session='chat_1',action=pb.ASSERT,value='February',recorded=1500),
        _e(g,'main',2,session='chat_2',action=pb.CHALLENGE,value='January',
           origin=pb.MODEL_HYPOTHESIS,recorded=1800),
        _e(g,'rival',2,session='chat_1',action=pb.EXPIRE,value='February',recorded=2400),
        _e(g,'main',3,session='chat_0',action=pb.CONFIRM,value='January',recorded=2800),
        _e(g,'main',4,session='chat_3',action=pb.TEMPORAL_CORRECT,value='January',
           recorded=3500,effective=900,corrects='deadline_main_03'),
        _e(g,'hypothesis',1,session='chat_4',action=pb.ASSERT,
           value='March maybe',recorded=3700,origin=pb.MODEL_HYPOTHESIS,
           uncertainty=pb.CONDITIONAL,note='Conditional, not approved by user.'),
        _e(g,'hypothesis',2,session='chat_5',action=pb.RETRACT,
           value='March maybe',recorded=4200,origin=pb.MODEL_HYPOTHESIS),
    ),(
        _case('nothing yet',800,5000),
        _case('backdating not known',950,3400),
        _case('backdating is known',950,3500,old),
        _case('before rival',1400,5000,old),
        _case('rival begins',1500,5000,old,other,conflicts=conflict),
        _case('challenge begins',1800,5000,_label(g,'January',status=pb.DISPUTED),other,conflicts=conflict),
        _case('rival expires',2400,5000,_label(g,'January',status=pb.DISPUTED)),
        _case('confirmed',2800,5000,old),
        _case('conditional alternative',3700,5000,old,extra,conflicts=second),
        _case('conditional withdrawn',4200,5000,old),
        _case('known cutoff before rival',2100,1400,old),
        _case('known cutoff during rivalry',2100,1700,old,other,conflicts=conflict),
        _case('known cutoff during dispute',2100,2000,_label(g,'January',status=pb.DISPUTED),other,conflicts=conflict),
        _case('known cutoff before expiration',3000,2399,_label(g,'January',status=pb.DISPUTED),other,conflicts=conflict),
        _case('known cutoff after expiration',3000,2500,_label(g,'January',status=pb.DISPUTED)),
        _case('known cutoff before hypothesis',4000,3600,old),
        _case('known cutoff hypothesis',4000,4000,old,extra,conflicts=second),
    ))

    g='backdate'; alpha=_label(g,'phase-A'); beta=_label(g,'phase-B')
    gamma=_label(g,'conditional-C','alternative',origin=pb.MODEL_HYPOTHESIS,
                 uncertainty=pb.CONDITIONAL)
    edge=((f'{g}_alternative',f'{g}_main'),)
    backdate=_finish(g,(
        _e(g,'main',1,session='chat_0',action=pb.ASSERT,value='phase-A',recorded=1000,until=3000),
        _e(g,'alternative',1,session='chat_1',action=pb.ASSERT,
           value='conditional-C',recorded=2700,until=3400,
           origin=pb.MODEL_HYPOTHESIS,uncertainty=pb.CONDITIONAL,
           note='Contingent proposal in another conversation.'),
        _e(g,'alternative',2,session='chat_2',action=pb.EXPIRE,
           value='conditional-C',recorded=3400,origin=pb.MODEL_HYPOTHESIS),
        _e(g,'main',2,session='chat_3',action=pb.SUPERSEDE,value='phase-B',recorded=4000),
        _e(g,'main',3,session='chat_4',action=pb.TEMPORAL_CORRECT,
           value='phase-B',recorded=4500,effective=2200,corrects='backdate_main_02'),
        _e(g,'main',4,session='chat_5',action=pb.CHALLENGE,value='phase-B',
           recorded=5000,origin=pb.MODEL_HYPOTHESIS),
        _e(g,'main',5,session='chat_3',action=pb.CONFIRM,value='phase-B',recorded=5600),
    ),(
        _case('before start',900,6000),_case('initial',1000,6000,alpha),
        _case('pre backdate start',2199,6000,alpha),
        _case('corrected start',2200,6000,beta),
        _case('alternative not started',2699,6000,beta),
        _case('alternative overlap',2700,6000,beta,gamma,conflicts=edge),
        _case('old interval ends',3000,6000,beta,gamma,conflicts=edge),
        _case('alternative last instant',3399,6000,beta,gamma,conflicts=edge),
        _case('alternative expired',3400,6000,beta),
        _case('challenge now disputed',5000,6000,_label(g,'phase-B',status=pb.DISPUTED)),
        _case('user confirmed',5600,6000,beta),
        _case('before correction known',2500,4499,alpha),
        _case('after correction known',2500,4500,beta),
        _case('before alternative known',2999,2699,alpha),
        _case('alternative known but correction not',2999,4000,alpha,gamma,conflicts=edge),
        _case('after correction with alternative',3000,4600,beta,gamma,conflicts=edge),
        _case('after model challenge but before confirmation',5500,5500,
              _label(g,'phase-B',status=pb.DISPUTED)),
    ))

    g='imports'; local=_label(g,'local-only'); remote=_label(g,'cloud-auto','imported',
             origin=pb.IMPORT_OBSERVED,uncertainty=pb.EXPLICITLY_UNCERTAIN)
    e=((f'{g}_imported',f'{g}_main'),)
    imports=_finish(g,(
        _e(g,'main',1,session='chat_0',action=pb.ASSERT,value='local-only',recorded=1000),
        _e(g,'imported',1,session='chat_1',action=pb.ASSERT,value='cloud-auto',
           recorded=1500,origin=pb.IMPORT_OBSERVED,
           uncertainty=pb.EXPLICITLY_UNCERTAIN,note='Imported, chronology unverified.'),
        _e(g,'main',2,session='chat_0',action=pb.SUPERSEDE,value='local-plus-backup',recorded=2100),
        _e(g,'imported',2,session='chat_2',action=pb.CHALLENGE,
           value='cloud-auto',recorded=2600,origin=pb.MODEL_HYPOTHESIS),
        _e(g,'main',3,session='chat_3',action=pb.CHALLENGE,
           value='local-plus-backup',recorded=2700,origin=pb.MODEL_HYPOTHESIS),
        _e(g,'main',4,session='chat_4',action=pb.CONFIRM,
           value='local-plus-backup',recorded=3000,origin=pb.HOST_OBSERVED),
        _e(g,'imported',3,session='chat_1',action=pb.RETRACT,
           value='cloud-auto',recorded=3300,origin=pb.IMPORT_OBSERVED),
        _e(g,'main',5,session='chat_5',action=pb.RETRACT,
           value='local-plus-backup',recorded=4000),
    ),(
        _case('initial',1000,5000,local),
        _case('before imported',1499,5000,local),
        _case('imported contradiction',1500,5000,local,remote,conflicts=e),
        _case('human goal shift',2100,5000,_label(g,'local-plus-backup'),remote,conflicts=e),
        _case('import challenged',2600,5000,_label(g,'local-plus-backup'),
              _label(g,'cloud-auto','imported',status=pb.DISPUTED,
                     origin=pb.IMPORT_OBSERVED,uncertainty=pb.EXPLICITLY_UNCERTAIN),conflicts=e),
        _case('both disputed',2700,5000,_label(g,'local-plus-backup',status=pb.DISPUTED),
              _label(g,'cloud-auto','imported',status=pb.DISPUTED,
                     origin=pb.IMPORT_OBSERVED,uncertainty=pb.EXPLICITLY_UNCERTAIN),conflicts=e),
        _case('host confirms not demote user',3000,5000,_label(g,'local-plus-backup'),
              _label(g,'cloud-auto','imported',status=pb.DISPUTED,
                     origin=pb.IMPORT_OBSERVED,uncertainty=pb.EXPLICITLY_UNCERTAIN),conflicts=e),
        _case('import retracted',3300,5000,_label(g,'local-plus-backup')),
        _case('human retracts',4000,5000),
        _case('known cutoff before import',4500,1499,local),
        _case('known cutoff contradiction',4500,2000,local,remote,conflicts=e),
        _case('known cutoff stale user',4500,2500,_label(g,'local-plus-backup'),remote,conflicts=e),
        _case('known cutoff model challenge',4500,2800,
              _label(g,'local-plus-backup',status=pb.DISPUTED),
              _label(g,'cloud-auto','imported',status=pb.DISPUTED,
                     origin=pb.IMPORT_OBSERVED,uncertainty=pb.EXPLICITLY_UNCERTAIN),conflicts=e),
        _case('known cutoff host confirmation',4500,3000,_label(g,'local-plus-backup'),
              _label(g,'cloud-auto','imported',status=pb.DISPUTED,
                     origin=pb.IMPORT_OBSERVED,uncertainty=pb.EXPLICITLY_UNCERTAIN),conflicts=e),
        _case('known cutoff imported retraction',4500,3500,_label(g,'local-plus-backup')),
        _case('known cutoff user retraction',4500,4000),
    ))
    return goals,deadline,backdate,imports


def query(case: LongCase) -> pb.AsOfQuery:
    return pb.AsOfQuery(schema_version=1,scope_id=SCOPE,
        valid_at_ms=case.valid_at_ms,known_at_ms=case.known_at_ms)


def filtered_projection(report: pb.HistoricalProjection, subject: str) -> tuple:
    selected=tuple(sorted((Expected(v.claim_id,v.value_text,v.status,v.origin,v.uncertainty_kind)
        for v in report.claims if v.subject_id==subject and v.predicate==PREDICATE),
        key=lambda c:c.claim_id))
    identifiers={x.claim_id for x in selected}
    conflicts=tuple(sorted(tuple(sorted((p.first_claim_id,p.second_claim_id)))
        for p in report.conflicts
        if p.subject_id==subject and p.predicate==PREDICATE
        and p.first_claim_id in identifiers and p.second_claim_id in identifiers))
    return selected,conflicts


def expected(case: LongCase) -> tuple:
    return (tuple(sorted(case.values,key=lambda v:v.claim_id)),
            tuple(sorted(tuple(sorted(edge)) for edge in case.conflicts)))


def oracle_digest(scenarios: tuple[LongScenario,...] | None = None) -> str:
    scenarios = long_scenarios() if scenarios is None else scenarios
    blocks=[]
    for scenario in scenarios:
        blocks.append({'group':scenario.name,'subject':scenario.subject_id,
            'events':[e.SerializeToString(deterministic=True).hex() for e in scenario.events],
            'cases':[(c.name,c.valid_at_ms,c.known_at_ms,
                      [(v.claim_id,v.value,v.status,v.origin,v.uncertainty) for v in c.values],
                      c.conflicts) for c in scenario.cases]})
    return sha256(json.dumps(blocks,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def evaluate() -> dict:
    scenarios=long_scenarios()
    counts={'C07':0,'chronological':0,'effective':0}
    failures=[]
    conflict_expected=0
    comparison_count=0
    for scenario in scenarios:
        state=StateLedger(SCOPE)
        state.apply_batch(scenario.events)
        target={e.claim_id for e in scenario.events if e.subject_id==scenario.subject_id and e.predicate==PREDICATE}
        for case in scenario.cases:
            want=expected(case)
            report=project_as_of(state,query(case))
            got=filtered_projection(report,scenario.subject_id)
            if got == want:counts['C07']+=1
            else:failures.append(f'{scenario.name}/{case.name}')
            if case.conflicts:conflict_expected+=1
            for name,baseline in [('chronological',chronological_register),('effective',effective_clock_register)]:
                equivalent=Case(case.name,case.valid_at_ms,case.known_at_ms,(),())
                claims,_=baseline(scenario.events,equivalent)
                selection=tuple(sorted((v for v in claims if v.claim_id in target),key=lambda v:v.claim_id))
                # Baselines do not emit explicit conflict edges; compare FULL selected answer.
                if (selection,()) == want:counts[name]+=1
            comparison_count+=1
    return {'evaluation_tier':'hand_annotated_synthetic_multiconversation_no_model',
            'golden_sha256':oracle_digest(scenarios),
            'scenarios':len(scenarios),'events':sum(len(x.events) for x in scenarios),
            'queries':comparison_count,'positive_conflict_queries':conflict_expected,
            'synthetic_sessions':len({e.source.session_id for s in scenarios for e in s.events}),
            'exact_target_answer_correct':counts,'C07_oracle_mismatches':failures,
            'no_model_or_Lu_executed':True,
            'limitations':['Gold labels cover one declared subject/predicate per query; background state is not independently annotated.',
                'All background evidence is still validated by full host-fenced publication.',
                'Synthetic session IDs and source hashes are not Lu authentication.',
                'Chronological/effective baselines lack conflict, provenance and security guarantees.',
                'No natural-language ambiguity classification, user study, native Rust or model run.']}
