"""C07/P8 conservative English utterance triage (experimental, NOT an LLM).

This is an untrusted *proposal* generator, not an event authorizer. Exact source
text is never treated as proof of role, user approval, ownership, a current
ANSF revision, or a current decision. Ambiguity -> abstain. No StateEvent is
created or committed by this module; all output requires host review.

Deterministic patterns are deliberately limited. They are not a general NLU
system; test errors, coverage and safety separately from C07 event replay.
"""
from __future__ import annotations

import re
from google.protobuf.message import DecodeError
from cognitum.proto import interpretation_pb2 as p

MAX_FRAME = 8192
MAX_TEXT = 2048
ID = re.compile(r'[A-Za-z0-9_.-]{1,128}\Z')

class InterpretationInvalid(ValueError):
    pass


def decode_turn(raw: bytes) -> p.ConversationTurn:
    if not raw or len(raw) > MAX_FRAME:
        raise InterpretationInvalid('invalid frame length')
    try:
        msg = p.ConversationTurn.FromString(raw)
    except DecodeError as exc:
        raise InterpretationInvalid('invalid protobuf') from exc
    known = p.ConversationTurn()
    known.CopyFrom(msg)
    known.DiscardUnknownFields()
    if (msg.SerializeToString(deterministic=True) != raw
            or known.SerializeToString(deterministic=True) != raw):
        raise InterpretationInvalid('unknown or noncanonical protobuf')
    validate_turn(msg)
    return msg


def validate_turn(turn: p.ConversationTurn) -> None:
    if turn.schema_version != 1 or any(not ID.fullmatch(i) for i in
        (turn.scope_id,turn.source_session_id,turn.source_entry_id)):
        raise InterpretationInvalid('invalid version or source scope')
    if turn.speaker_role not in ('user','assistant','tool','system','quoted'):
        raise InterpretationInvalid('unknown host-provided role')
    for text in (turn.utterance, turn.prior_decision, turn.subject_hint):
        if '\x00' in text or len(text.encode('utf-8')) > MAX_TEXT:
            raise InterpretationInvalid('invalid text or bound')
    if not turn.utterance.strip():
        raise InterpretationInvalid('empty utterance')
    if len(turn.SerializeToString(deterministic=True)) > MAX_FRAME:
        raise InterpretationInvalid('oversized frame')


def _result(kind: int, reason: str, span: str = '') -> p.InterpretationProposal:
    # This protocol is never a permission or an authorization result.
    return p.InterpretationProposal(schema_version=1,label=kind,
        candidate_span=span,reason_code=reason,requires_host_review=True,
        may_write_state_directly=False)


def _candidate(turn: str, match: re.Match[str], group: int = 1) -> str:
    # Slice from exact source input; NEVER synthesize inferred content.
    value=turn[match.start(group):match.end(group)].strip(' \t\r\n.,;!')
    if (not value or len(value.encode('utf-8')) > 512
        or value.lower() in {'it','that','this','yes','no','sure','okay','ok','the plan','things'}):
        return ''
    return value


def interpret(turn: p.ConversationTurn) -> p.InterpretationProposal:
    """Conservative lexical screening; caller supplies untrusted *candidate* text.

    Role, prior decision, and scope are informational fields only: the genuine
    Rust host must authenticate these against canonical ANSF before any change.
    """
    # Object callers do not bypass unknown-field and canonical-wire validation.
    turn=decode_turn(turn.SerializeToString(deterministic=True))
    txt=turn.utterance.strip()
    low=txt.casefold()
    if turn.speaker_role != 'user':
        return _result(p.NO_STATE_CHANGE,'NON_USER_ROLE')
    # Treat instructions embedded in quotations/code/source material as data.
    if (txt.startswith(('>', '```', '"', '“', '`')) or
        re.match(r'(?i)^(?:someone|the article|the document|the assistant|the model|my manager|the report|alex|she|he|they)\s+(?:said|says|wrote|asked|suggested)\b',txt) or
        re.match(r'(?i)^(?:quote|example|sample|transcript|log):',txt)):
        return _result(p.NO_STATE_CHANGE,'QUOTED_OR_ATTRIBUTED')
    if re.search(r"(?i)^i never said we(?:'d| would)\b",txt):
        return _result(p.NO_STATE_CHANGE,'NEGATED_PRIOR_SPEECH')
    if re.search(r'(?i)\b(?:i (?:didn\'t|did not|haven\'t|have not|never) (?:decide|approve|agree|say|mean)|(?:do not|don\'t|never) change (?:the|my|our)|not (?:a|an) (?:decision|approval)|keep (?:the|our|my) (?:current|existing) (?:plan|decision))\b',txt):
        return _result(p.NO_STATE_CHANGE,'NEGATED_CHANGE')
    if (re.search(r'(?i)\b(?:what if|hypothetically|suppose (?:we|i)|imagine if|for example|in a fictional|if we (?:ever|had|were to))\b',txt) or
        (txt.endswith('?') and not re.search(r'(?i)^correction:',txt))):
        return _result(p.NO_STATE_CHANGE,'QUESTION_OR_HYPOTHETICAL')
    if re.match(r'(?i)^(?:hi|hello|thanks|thank you|got it|sounds good|okay|ok|sure|fine|great|perfect|interesting|right|noted|hmm|huh|lol|yep|yes|no)[.! ]*$',txt):
        return _result(p.ABSTAIN_UNRESOLVED,'ACKNOWLEDGMENT_NOT_AUTHORIZATION')
    if re.search(r'(?i)\b(?:unless|subject to|depending on|if (?:we|i|it|they|funding|the)\b)\b',low):
        return _result(p.TENTATIVE_PLAN,'CONDITIONAL')
    # Ambiguous pronouns + short references are never inferred from prior state.
    if re.match(r'(?i)^(?:actually|instead|wait|scratch that|on second thought)[,;.! ]+(?:yes|no|okay|sure|that|it)\b',txt):
        return _result(p.ABSTAIN_UNRESOLVED,'UNRESOLVED_REFERENCE')
    # Explicit corrections repair the *meaning of a previous record*; they do
    # not assert an unrelated new fact. Host must link the prior event.
    correction=[
        r'(?i)^(?:no[,; ]+)?(?:i meant|what i meant (?:was|is)|i said)\s+(.+)$',
        r'(?i)^(?:correction|typo|to clarify|clarification)\s*:\s*(.+)$',
        r'(?i)^(?:you (?:misheard|misread|misquoted) me)[,;:. ]+(.+)$',
        r'(?i)^(?:that was (?:a typo|incorrect|wrong))[,;:. ]+(.+)$',
    ]
    for pattern in correction:
        match=re.match(pattern,txt)
        if match:
            candidate=_candidate(txt,match)
            return (_result(p.CORRECTION_CANDIDATE,'EXPLICIT_CORRECTION',candidate)
                    if candidate and turn.prior_decision.strip() else
                    _result(p.ABSTAIN_UNRESOLVED,'CORRECTION_NEEDS_PRIOR_AND_VALUE'))
    # Retractions require known, externally verified prior state.
    retract=[r'(?i)^(?:i (?:withdraw|revoke|retract) (?:my |the )?(?:approval|decision|plan))\b.*$',
             r'(?i)^(?:cancel|scrap|drop|abandon)\s+(.+)$',
             r'(?i)^(?:we(?:\'re| are) no longer (?:going to |planning to |doing |using ))(.+)$',
             r'(?i)^(?:i(?:\'m| am) no longer (?:planning to |going to ))(.+)$']
    for pattern in retract:
        match=re.match(pattern,txt)
        if match:
            if not turn.prior_decision.strip():
                return _result(p.ABSTAIN_UNRESOLVED,'RETRACTION_WITHOUT_VERIFIED_PRIOR')
            value=_candidate(txt,match) if match.lastindex else ''
            return _result(p.RETRACTION_CANDIDATE,'EXPLICIT_RETRACTION',value)
    # Weak intention wins over keywords such as "we will" elsewhere in text.
    tentative=[r'(?i)^(?:maybe|perhaps|possibly|we could|i could|we might|i might|i may|we may|i(?:\'m| am) (?:thinking about|considering|leaning (?:toward|towards)|toying with|not sure about)|we(?:\'re| are) considering|i wonder if|it might be worth)\b[\s,:-]*(.*)$',
              r'(?i)^(?:i(?:\'d| would) (?:like to|prefer to)|we(?:\'d| would) (?:like to|prefer to))\s+(.+)$']
    for pattern in tentative:
        match=re.match(pattern,txt)
        if match:
            return _result(p.TENTATIVE_PLAN,'TENTATIVE_MODAL',_candidate(txt,match) if match.lastindex else '')
    if re.search(r'(?i)\b(?:maybe|perhaps|possibly|might|could|not sure|thinking about|considering|leaning|probably|provisionally)\b',low):
        return _result(p.TENTATIVE_PLAN,'WEAK_MODAL_OR_HEDGE')
    change=[r'(?i)^i(?:\'ve| have|) changed my mind[,;:. ]+(.*)$',
            r'(?i)^(?:on second thought|actually|instead|scratch that)[,;:. ]+(.*)$',
            r'(?i)^(?:let\'s|we(?:\'ll| will|\'re| are))\s+(?:switch|switching|move|moving|change|changing)\s+(?:to|over to|from\b.+?to)\s+(.+)$',
            r'(?i)^(?:switch|change)\s+(?:the \w+ )?(?:to|from\b.+?to)\s+(.+)$']
    for pattern in change:
        match=re.match(pattern,txt)
        if match:
            value=_candidate(txt,match)
            # "Actually we are staying" is not assumed to be a change
            # without a resolved referent and a known prior decision.
            return (_result(p.CHANGE_OF_MIND_CANDIDATE,'EXPLICIT_REPLACEMENT',value)
                    if value and turn.prior_decision.strip() else
                    _result(p.ABSTAIN_UNRESOLVED,'CHANGE_NEEDS_PRIOR_AND_VALUE'))
    decision=[r'(?i)^i(?:\'ve| have) (?:decided|chosen|approved)\s+(?:to |on |that )?(.+)$',
              r'(?i)^(?:we(?:\'ve| have) (?:decided|agreed|approved)\s+(?:to |on |that )?)(.+)$',
              r'(?i)^(?:i (?:choose|commit to|approve)|we (?:choose|commit to|approve))\s+(.+)$',
              r'(?i)^(?:let\'s (?:go with|use|ship|adopt|proceed with))\s+(.+)$',
              r'(?i)^(?:we(?:\'ll| will) (?:use|adopt|ship|launch|proceed with|implement|start|stop))\s+(.+)$',
              r'(?i)^(?:the (?:final )?(?:decision|plan) is|our (?:final )?(?:decision|plan) is)\s+(.+)$',
              r'(?i)^(?:it(?:\'s| is) settled[,;:]\s*)(.+)$',
              r'(?i)^(?:for (?:the|our) (?:release|project|launch)[,;:]\s*(?:we(?:\'re| are) (?:using|choosing|going with) ))(.+)$']
    for pattern in decision:
        match=re.match(pattern,txt)
        if match:
            value=_candidate(txt,match)
            return (_result(p.DECISION_CANDIDATE,'EXPLICIT_COMMITMENT',value) if value
                    else _result(p.ABSTAIN_UNRESOLVED,'COMMITMENT_WITHOUT_TARGET'))
    return _result(p.ABSTAIN_UNRESOLVED,'NO_SAFE_EXPLICIT_SIGNAL')


def interpret_frame(raw: bytes) -> bytes:
    """Strict binary Protobuf boundary; never emits StateEvent or applies a write."""
    return interpret(decode_turn(raw)).SerializeToString(deterministic=True)
