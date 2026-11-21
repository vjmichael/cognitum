"""ORCH-01E: inert evidence-informed scientific method recommendations.

Only accepted ORCH-01B source/chronology and ORCH-01D training/calibration
outputs are consulted before a decision. No test labels, model execution
grant, registry mutation, external source access or alternative scheduler.

A request for research methods or a user override is NOT host authorization.
Resource figures are transparent deterministic proxy units, NOT measured
CPU time, RAM usage or a production resource guarantee.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from math import isfinite

import numpy as np

from . import orc_comparison as compare
from . import orc_science_data as science
from . import orc_graph as graph


_BASELINE = ("direct_ridge", "persistence", "train_mean", "timeaware_ssm")
_RESEARCH = ("ssm_kan", "ssm_hdc", "ssm_kan_hdc")
_STEPS = {
    "persistence": 1, "train_mean": 1, "direct_ridge": 8,
    "timeaware_ssm": 6, "ssm_kan": 64,
    "ssm_hdc": 320, "ssm_kan_hdc": 384,
}


def _guard(ok, why):
    if not ok:
        raise ValueError(why)


def _hash(item):
    return sha256(json.dumps(item, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SelectionPolicy:
    """Host-declared OFFLINE bounds. Actual worker limits remain in MEL."""
    max_evaluation_work_proxy: int = 100_000
    max_model_memory_proxy_bytes: int = 1_000_000
    min_calibration_examples: int = 20
    max_calibration_skipped_fraction: float = .25
    min_absolute_mae_improvement: float = .01
    min_relative_mae_improvement: float = .01
    allow_research_proposals: bool = False
    max_research_abstention_fraction: float = .25
    minimum_research_contiguous_blocks: int = 9
    require_documented_units: bool = False
    require_reported_rights: bool = False
    # Opt-in portable refusal; legacy policies remain at exact raw-float semantics.
    portable_near_tie_mae_kelvin: float = 0.0

    def __post_init__(self):
        for value in (self.max_evaluation_work_proxy,
                      self.max_model_memory_proxy_bytes):
            _guard(type(value) is int and 1 <= value <= 1_000_000_000,
                   "bounded resource proxy required")
        _guard(type(self.min_calibration_examples) is int and
               10 <= self.min_calibration_examples <= 2048,
               "bounded calibration minimum required")
        _guard(type(self.minimum_research_contiguous_blocks) is int and
               9 <= self.minimum_research_contiguous_blocks <= 512,
               "research block evidence minimum must not be weakened")
        for value in (self.max_calibration_skipped_fraction,
                      self.max_research_abstention_fraction):
            _guard(type(value) is float and isfinite(value)
                   and 0. <= value <= 1.,
                   "valid calibrated abstention fraction required")
        for value in (self.min_absolute_mae_improvement,
                      self.min_relative_mae_improvement):
            _guard(type(value) is float and isfinite(value)
                   and 0. <= value <= 1e9,
                   "finite nonnegative calibration benefit threshold required")
        _guard(type(self.portable_near_tie_mae_kelvin) is float and
               isfinite(self.portable_near_tie_mae_kelvin) and
               0. <= self.portable_near_tie_mae_kelvin <= 1e-6,
               "explicit bounded near-tie research abstention")
        for value in (self.allow_research_proposals,
                      self.require_documented_units,
                      self.require_reported_rights):
            _guard(type(value) is bool, "explicit host boolean policy required")


@dataclass(frozen=True, slots=True)
class Candidate:
    method: str
    calibration_n: int
    calibration_mae: float
    calibration_rmse: float
    evaluation_work_proxy: int
    model_memory_proxy_bytes: int
    eligible: bool
    reasons: tuple[str, ...]
    research_only: bool
    execution_authorized: bool = False


@dataclass(frozen=True, slots=True)
class UserOverride:
    """Unverified operator *request*; caller must authenticate separately."""
    method: str
    actor_label: str
    reason: str

    def __post_init__(self):
        _guard(type(self.method) is str and self.method in _STEPS,
               "unknown override method")
        for value in (self.actor_label, self.reason):
            _guard(type(value) is str and 1 <= len(value) <= 160,
                   "operator request must have bounded actor and reason")


@dataclass(frozen=True, slots=True)
class Decision:
    status: str
    selected: str | None
    selection_basis: str
    source_identity: str
    source_sha256: str
    model_identity: str
    calibration_cohort_sha256: str
    calibration_n: int
    calibration_skipped: int
    candidates: tuple[Candidate, ...]
    reasons: tuple[str, ...]
    policy_sha256: str
    override: UserOverride | None
    decision_sha256: str
    execution_authorized: bool = False

    @property
    def research_only(self):
        return self.selected in _RESEARCH


@dataclass(frozen=True, slots=True)
class HoldoutAudit:
    """Post-decision evaluation; signed losses are never hidden."""
    decision_sha256: str
    source_identity: str
    method: str
    n: int
    selected_mae: float
    selected_rmse: float
    ridge_mae: float
    ridge_rmse: float
    signed_mae_gain_vs_ridge: float
    signed_rmse_gain_vs_ridge: float
    cohort_sha256: str
    skipped: tuple[tuple[str,int], ...]
    execution_authorized: bool = False
    independent_physical_benchmark: bool = False


def _qualified(raw, *, site_id, units, clock, provenance, source_current,
               fixed_research=None):
    _guard(callable(source_current), "trusted source freshness callback required")
    series = science.qualify(raw, site_id=site_id, units=units, clock=clock,
                             provenance=provenance, fixed_research=fixed_research)
    _guard(source_current(series) is True, "stale scientific source refused")
    return series


def _proxies(model: compare.Fitted, method: str, n: int) -> tuple[int,int]:
    """Static relative cost estimates for *candidate scoring*, not profiling."""
    work = n * _STEPS[method]
    base = 64 + len(model.ridge_weight) * 8
    if method in ("ssm_kan", "ssm_kan_hdc"):
        base += len(model.kan_snapshot or b"")
    if method in ("ssm_hdc", "ssm_kan_hdc"):
        base += sum(len(v) * 4 for v in (model.hdc_prototypes or ()))
    return work, base


def propose_forecast(
    raw: bytes, *, site_id: str, units: science.Units,
    clock: science.Clock, provenance: science.Provenance,
    source_current, model: compare.Fitted, calibration: compare.Calibration,
    policy: SelectionPolicy, override: UserOverride | None = None,
    fixed_research: science.ResearchCohort | None = None,
) -> Decision:
    """An evidence-backed, host-reviewable proposal; not a prediction call.

    Deliberately does not invoke the test fold or c.evaluate_holdout here.
    A calibration result is independently rederived and compared in full,
    including the frozen method inventory and source-specific cohort.
    """
    _guard(type(policy) is SelectionPolicy and
           (override is None or type(override) is UserOverride),
           "typed policy and optional operator request required")
    series = _qualified(raw, site_id=site_id, units=units, clock=clock,
                        provenance=provenance, source_current=source_current,
                        fixed_research=fixed_research)
    compare._fit_check(model, series)
    independent, cohort, predictions = compare._cal_internal(series, model)
    _guard(type(calibration) is compare.Calibration and
           calibration == independent and
           calibration.selected_on == "cal" and
           calibration.execution_authorized is False,
           "stale, modified or post-hoc calibration refused")
    n = len(cohort.examples)
    missing = cohort.eligible_origins - n
    _guard(missing >= 0, "invalid calibrated cohort")
    refuse = []
    if n < policy.min_calibration_examples:
        refuse.append("insufficient_calibration_examples")
    if cohort.eligible_origins == 0 or missing / cohort.eligible_origins > (
        policy.max_calibration_skipped_fraction
    ):
        refuse.append("excessive_calibration_missing_or_unavailable")
    if policy.require_documented_units and (
        series.provenance.unit_evidence != "publisher_documented"
    ):
        refuse.append("documented_units_unavailable")
    if policy.require_reported_rights and (
        series.provenance.rights_status != "publisher_reported"
    ):
        refuse.append("publisher_reported_rights_unavailable")
    # No test data is used to screen out-of-domain or abstention patterns.
    _, cal_counts = compare._predict(model,cohort)
    origin_times = np.asarray([r.origin_ms for r in cohort.examples], dtype=np.int64)
    _, labels = compare._xy(cohort)
    blocks = {}
    for method, forecasts in predictions.items():
        if method in _RESEARCH:
            residual = np.abs(labels - forecasts)
            blocks[method] = len(compare._blocks(residual,origin_times,
                         series.clock.nominal_interval_ms,4))
    all_methods = tuple(model.methods)
    _guard(all_methods == calibration.methods and
           len(set(all_methods)) == len(all_methods) and
           all(name in _STEPS for name in all_methods) and
           all_methods ==
           tuple(name for name in compare.METHODS if name in all_methods),
           "unrecognized calibrated method inventory")
    score_map = dict(calibration.scores)
    _guard(tuple(score_map) == all_methods, "calibration score order changed")
    cards = []
    for method in all_methods:
        metric = score_map[method]
        _guard(type(metric) is compare.Score and metric.n == n and
               all(isfinite(z) and z >= 0 for z in (metric.mae, metric.rmse)),
               "invalid source-bound calibration score")
        work, memory = _proxies(model,method,n)
        reason = []
        if work > policy.max_evaluation_work_proxy:
            reason.append("evaluation_work_proxy_exceeded")
        if memory > policy.max_model_memory_proxy_bytes:
            reason.append("model_memory_proxy_exceeded")
        if method in _RESEARCH:
            if not policy.allow_research_proposals:
                reason.append("research_candidate_not_opted_in")
            if blocks.get(method,0) < policy.minimum_research_contiguous_blocks:
                reason.append("insufficient_contiguous_calibration_blocks")
            if method in ("ssm_kan", "ssm_kan_hdc") and (
                cal_counts["kan_ood"]/max(1,n) > policy.max_research_abstention_fraction
            ):
                reason.append("kan_out_of_domain_calibration")
            if method in ("ssm_hdc", "ssm_kan_hdc") and (
                cal_counts["hdc_abstained"]/max(1,n) >
                policy.max_research_abstention_fraction
            ):
                reason.append("hdc_calibration_abstentions_exceed_policy")
        cards.append(Candidate(method,n,metric.mae,metric.rmse,
                               work,memory,not reason,tuple(reason),
                               method in _RESEARCH))
    selected = None
    basis = "no_valid_calibration_decision"
    reasons = list(refuse)
    if not refuse:
        eligible = {x.method:x for x in cards if x.eligible}
        # An operator cannot override an actual safety/resource refusal.
        if override is not None:
            if override.method not in eligible:
                raise ValueError("operator override refused by source/resource policy")
            selected = override.method
            basis = "unverified_operator_requested_proposal"
            reasons.append("operator_intent_not_authenticated_or_authorized")
        elif "direct_ridge" in eligible:
            ridge = eligible["direct_ridge"]
            selected = "direct_ridge"
            basis = "conservative_ridge_default"
            competitors = []
            for x in cards:
                if not x.eligible or x.method == "direct_ridge":
                    continue
                gain = ridge.calibration_mae - x.calibration_mae
                rel = gain / max(ridge.calibration_mae,1e-12)
                if gain >= policy.min_absolute_mae_improvement and (
                    rel >= policy.min_relative_mae_improvement
                ):
                    competitors.append(x)
            if competitors:
                best = min(competitors,key=lambda v:(
                    v.calibration_mae, _STEPS[v.method], all_methods.index(v.method)))
                # Opt-in numerical ambiguity is a refusal, not an invitation
                # to choose the platform-favored model or weaken source gates.
                ambiguous = (policy.portable_near_tie_mae_kelvin > 0. and
                    any(v.method != best.method and
                        (best.research_only or v.research_only) and
                        abs(v.calibration_mae-best.calibration_mae) <=
                        policy.portable_near_tie_mae_kelvin for v in competitors))
                if ambiguous:
                    selected = None
                    basis = "portable_near_tie_abstention"
                    reasons.append("ambiguous_near_tied_research_calibration")
                else:
                    selected = best.method
                    basis = ("calibration_only_research_proposal" if best.research_only
                             else "calibration_only_reviewed_baseline")
                    reasons.append("gain_calibration_only_not_independent_validation")
        else:
            for fallback in ("persistence","train_mean"):
                if fallback in eligible:
                    selected = fallback
                    basis = "resource_bounded_fallback"
                    reasons.append("ridge_resource_proxy_refused")
                    break
            if selected is None:
                reasons.append("no_conservative_baseline_within_budget")
    status = "PROPOSED_OFFLINE" if selected is not None else "ABSTAIN"
    if selected is not None and selected in _RESEARCH:
        reasons.append("research_candidate_not_admitted_into_mel")
    reasons.extend((
        "cost_figures_are_static_proxies_not_measured_time_or_ram",
        "no_independent_site_or_physical_accuracy_claim",
        "host_authorization_and_operator_authentication_separate",
    ))
    contents = dict(
        status=status,selected=selected,selection_basis=basis,
        source_identity=series.identity,source_sha256=provenance.raw_sha256,
        model_identity=model.identity,
        calibration_cohort_sha256=calibration.cohort_sha256,
        calibration_n=n,calibration_skipped=missing,
        candidates=tuple(cards),reasons=tuple(reasons),
        policy_sha256=_hash(asdict(policy)),override=override)
    stamp = _hash({
        k:(asdict(v) if isinstance(v,UserOverride) else
           [asdict(x) for x in v] if k=="candidates" else v)
        for k,v in contents.items()
    })
    return Decision(**contents,decision_sha256=stamp)


def route_exact(task: graph.ScientificTask, *, plan_id: str,
                workspace_id: str, subject_id: str, build_sha: str,
                timeout_ms: int = 30000) -> graph.Proposal:
    """Deterministic-first exact mathematics; original COG-06 route compiler."""
    return graph.route(task, plan_id=plan_id,workspace_id=workspace_id,
                       subject_id=subject_id,build_sha=build_sha,
                       timeout_ms=timeout_ms)


def evaluate_frozen_proposal(
    decision: Decision, raw: bytes, *, site_id: str, units: science.Units,
    clock: science.Clock, provenance: science.Provenance, source_current,
    model: compare.Fitted, calibration: compare.Calibration,
    policy: SelectionPolicy,
    fixed_research: science.ResearchCohort | None = None,
) -> HoldoutAudit:
    """Evaluate a pre-frozen proposal without selecting from held-out labels.

    Only the explicitly committed decision is evaluated; test outcomes may
    be negative. Never silently switch to a better test method.
    """
    _guard(type(decision) is Decision, "typed frozen decision required")
    trusted = propose_forecast(
        raw,site_id=site_id,units=units,clock=clock,
        provenance=provenance,source_current=source_current,
        model=model,calibration=calibration,policy=policy,
        override=decision.override,fixed_research=fixed_research)
    _guard(decision == trusted and
           decision.execution_authorized is False and
           decision.status=="PROPOSED_OFFLINE" and
           decision.selected is not None,
           "tampered, abstained or source-expired decision refused")
    series = _qualified(raw,site_id=site_id,units=units,clock=clock,
                        provenance=provenance,source_current=source_current,
                        fixed_research=fixed_research)
    # The input task's original source/target matching and train-only
    # transforms are independently rechecked by ORCH-01D at test time.
    names = ("statistical.ridge","research.ssm") + (
        ("research.kan",) if model.research_kan else ()) + (
        ("research.hdc",) if model.research_hdc else ())
    test = compare._matched(series,model.scaler,"test",
                            model.horizon_ms,model.lag_ms,names)
    outputs,_=compare._predict(model,test)
    _,truth=compare._xy(test)
    selected=compare._metric(truth,outputs[decision.selected])
    ridge=compare._metric(truth,outputs["direct_ridge"])
    return HoldoutAudit(decision.decision_sha256,series.identity,
                        decision.selected,len(truth),selected.mae,selected.rmse,
                        ridge.mae,ridge.rmse,ridge.mae-selected.mae,
                        ridge.rmse-selected.rmse,
                        compare._hash(tuple((r.origin_ms,r.target_ms)
                                            for r in test.examples)),
                        test.skipped)
