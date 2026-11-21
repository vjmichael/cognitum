"""COG-ORCH-01D: bounded, offline matched-cohort scientific comparison.

This is an experimental *evaluation* layer, not a second MEL executor or
research tool authorization. It reuses ORCH-01B's source, as-of, fold and
feature rules, R4 ridge/elapsed-time SSM kernels, COG-04A KAN and HDC MAP.
Research KAN/HDC are never registered as MEL grants by this module.

A trained estimator is fitted ONLY on chronological train examples, the
candidate method is chosen ONLY on calibration examples and untouched test
examples are scored afterward. Uncertainty outputs are descriptive,
dependent-block *sensitivity diagnostics*, not conformal guarantees.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from math import ceil, isfinite, sqrt
import json
from time import perf_counter

import numpy as np

from . import orc_science_data as data
from .research.ssm_timeaware import ridge_fit, ridge_predict, ssm_zoh_rate
from .research.kan_trainable import Layer, Network, load_snapshot
from .research.hdc_algebra import Spec
from .research.hdc_associative import Cleanup

MAX_OBSERVATIONS = 2048
MAX_FEATURE_MAGNITUDE = 1000.
METHODS = ("persistence", "train_mean", "direct_ridge", "timeaware_ssm",
           "ssm_kan", "ssm_hdc", "ssm_kan_hdc")
_BASE = METHODS[:4]
_SEED = 5504


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("ascii")).hexdigest()


def _need(condition, problem):
    if not condition:
        raise ValueError(problem)


def _series(series):
    _need(type(series) is data.QualifiedSeries and
          80 <= len(series.rows) <= MAX_OBSERVATIONS,
          "bounded qualified scientific observations required")
    _need(type(series.provenance.raw_sha256) is str, "source content required")
    return series


def _batch(series, scaler, fold, horizon_ms, lag_ms, operation):
    split = data.split_chronological(series)
    contract = data.CandidateContract(operation, series.units)
    prepared = data.prepare_forecasts(series, split, scaler, contract,
                                      fold=fold, horizon_ms=horizon_ms,
                                      lag_ms=lag_ms)
    _need(prepared.eligible_origins >= 10 and len(prepared.examples) >= 10,
          "insufficient as-of forecast cohort")
    if prepared.examples:
        arr = np.asarray([r.feature_values for r in prepared.examples], dtype=float)
        _need(np.isfinite(arr).all() and
              np.max(np.abs(arr)) <= MAX_FEATURE_MAGNITUDE,
              "out-of-bounds standardized features")
    return prepared


def _matched(series, scaler, fold, horizon_ms, lag_ms, names):
    # Every candidate independently invokes the original strict source/fold
    # contract. A mismatch is an error, NEVER a silent sample intersection.
    equivalents = tuple(_batch(series, scaler, fold, horizon_ms, lag_ms,
                               operation) for operation in names)
    data.assert_matched_cohorts(*equivalents)
    return equivalents[0]


def _xy(batch):
    return (np.asarray([r.feature_values for r in batch.examples], dtype=np.float64),
            np.asarray([r.target for r in batch.examples], dtype=np.float64))


def _axes(x):
    lo = np.min(x,axis=0)
    hi = np.max(x,axis=0)
    _need(len(lo) == 2 and np.all(hi - lo >= 1e-5),
          "constant or degenerate train-only research feature domain")
    return lo, hi


def _hdc_code(row, lo, hi, symbols, spec):
    bins = np.minimum(3, np.floor(np.clip((row - lo)/(hi - lo), 0., 1.) * 4.).astype(int))
    return spec.bundle(np.stack((symbols[0,bins[0]],symbols[1,bins[1]])))


def _model_material(m):
    return {
        "schema": "orc.comparison.fit.v1", "source": m.source_identity,
        "source_sha256": m.source_sha256,
        "train_origin_sha256": m.train_origin_sha256,
        "horizon_ms": m.horizon_ms, "lag_ms": m.lag_ms,
        "train_cutoff_ms": m.train_cutoff_ms,
        "scaler": (m.scaler.mean, m.scaler.standard_deviation,
                   m.scaler.count, m.scaler.training_rows_sha256),
        "ridge": (m.ridge_mean, m.ridge_scale, m.ridge_weight),
        "ssm": (m.ssm_tau_seconds, m.ssm_train_mean),
        "research": (m.research_kan, m.research_hdc,
                     m.kan_snapshot_sha256, m.kan_domain,
                     m.kan_residual_scale, m.hdc_prototypes,
                     m.hdc_bias, m.hdc_post_kan_bias, m.correction_cap),
    }


@dataclass(frozen=True, slots=True)
class Fitted:
    source_identity: str
    source_sha256: str
    horizon_ms: int
    lag_ms: int
    train_cutoff_ms: int
    train_origin_sha256: str
    scaler: data.TrainScaler
    ridge_mean: tuple[float, ...]
    ridge_scale: tuple[float, ...]
    ridge_weight: tuple[float, ...]
    ssm_tau_seconds: float
    ssm_train_mean: float
    research_kan: bool
    research_hdc: bool
    kan_snapshot: bytes | None
    kan_snapshot_sha256: str | None
    kan_domain: tuple[tuple[float,float],...] | None
    kan_residual_scale: float
    hdc_prototypes: tuple[tuple[float,...],...] | None
    hdc_bias: tuple[float, float] | None
    hdc_post_kan_bias: tuple[float,float] | None
    correction_cap: float
    identity: str
    execution_authorized: bool = False

    @property
    def methods(self):
        return _BASE + (("ssm_kan",) if self.research_kan else ()) + (
            ("ssm_hdc",) if self.research_hdc else ()) + (
            ("ssm_kan_hdc",) if self.research_hdc and self.research_kan else ())


@dataclass(frozen=True, slots=True)
class Score:
    n: int
    mae: float
    rmse: float


@dataclass(frozen=True, slots=True)
class Calibration:
    model_identity: str
    source_identity: str
    methods: tuple[str,...]
    scores: tuple[tuple[str,Score],...]
    selected: str
    cohort_sha256: str
    selected_on: str = "cal"
    execution_authorized: bool = False


@dataclass(frozen=True, slots=True)
class IntervalAudit:
    status: str
    nominal: float
    calibration_blocks: int
    test_blocks: int
    radius: float | None
    origin_coverage: float | None
    simultaneous_block_coverage: float | None
    conditional_guarantee: bool = False


@dataclass(frozen=True, slots=True)
class DependenceAudit:
    status: str
    blocks: int
    mean_mae_gain: float
    bootstrap_95: tuple[float,float] | None
    confidence_proven: bool = False


@dataclass(frozen=True, slots=True)
class Evaluation:
    source_identity: str
    model_identity: str
    calibration: Calibration
    test_cohort_sha256: str
    test_scores: tuple[tuple[str,Score],...]
    selected_rmse_gain_vs_ridge: float
    selected_mae_gain_vs_ridge: float
    selected_interval: IntervalAudit
    ridge_interval: IntervalAudit
    paired_gain: DependenceAudit
    audit_counters: tuple[tuple[str,int],...]
    test_eligible_origins: int
    test_skipped: tuple[tuple[str,int],...]
    execution_authorized: bool = False
    limitations: tuple[str,...] = (
        "offline_research_only_no_mel_grant",
        "source_metadata_declared_not_original_sensor_authenticated",
        "selection_cal_only_test_evaluated_afterward",
        "confidence_intervals_descriptive_not_conditional_guarantees",
        "kan_hdc_training_not_physical_law_or_engine_production_admission",
        "not_orc_vs_ridge_independent_benchmark",
    )


def _fit_check(model, series):
    _series(series)
    _need(type(model) is Fitted and model.execution_authorized is False
          and model.source_identity == series.identity
          and model.source_sha256 == series.provenance.raw_sha256,
          "source-bound fitted model required")
    _need(model.scaler == data.fit_train_scaler(
        series, data.split_chronological(series))
        and model.train_cutoff_ms == model.scaler.cutoff_ms,
        "source/fold or train-only normalization changed")
    _need(_hash(_model_material(model)) == model.identity,
          "tampered model training identity")
    if model.kan_snapshot is not None:
        _need(model.kan_snapshot_sha256 == sha256(model.kan_snapshot).hexdigest(),
              "KAN snapshot sha mismatch")
    return model


def fit_train(series: data.QualifiedSeries, *, horizon_ms: int, lag_ms: int,
              research_kan: bool = False, research_hdc: bool = False) -> Fitted:
    """Train-only static methods; optional HDC/KAN are explicit research mode."""
    _series(series)
    _need(type(research_kan) is bool and type(research_hdc) is bool,
          "explicit research flags required")
    _need(type(horizon_ms) is int and type(lag_ms) is int
          and 1000 <= horizon_ms <= 30*86_400_000
          and 1000 <= lag_ms <= 30*86_400_000,
          "bounded physical elapsed-time horizon and exact lag")
    split = data.split_chronological(series)
    scaler = data.fit_train_scaler(series,split)
    names = ("statistical.ridge","research.ssm") + (
        ("research.kan",) if research_kan else ()) + (
        ("research.hdc",) if research_hdc else ())
    train = _matched(series,scaler,"train",horizon_ms,lag_ms,names)
    x,y = _xy(train)
    _need(len(y) >= 25 and np.all(np.isfinite(y)), "insufficient train targets")
    design = np.column_stack((x,np.ones(len(x))))
    ridge = ridge_fit(design,y)  # Reuse the accepted R4 research ridge kernel.
    origin = scaler.mean+scaler.standard_deviation*x[:,0]
    elapsed_seconds = horizon_ms/1000.
    candidates = tuple(t for t in (elapsed_seconds,elapsed_seconds*4,
                                   elapsed_seconds*16,elapsed_seconds*64)
                       if t <= 365*86_400)
    _need(bool(candidates), "SSM stable generator time domain")
    options = tuple((float(np.mean(np.abs(
        y - (scaler.mean + ssm_zoh_rate(t,elapsed_seconds) *
             (origin - scaler.mean))))),t) for t in candidates)
    tau = min(options,key=lambda q:(q[0],q[1]))[1]
    ssm = scaler.mean+ssm_zoh_rate(tau,elapsed_seconds)*(origin-scaler.mean)
    residual = y-ssm
    correction_cap = max(3*float(np.std(residual)),1e-8)
    kan_bytes=kan_sha=None; kan_domain=None; kan_scale=1.
    kan_train = np.zeros(len(x),dtype=float)
    if research_kan or research_hdc:
        lo,hi=_axes(x)
        kan_domain=tuple((float(a),float(b)) for a,b in zip(lo,hi))
    if research_kan:
        from numpy import zeros, ones
        layer = Layer("chebyshev",2,np.asarray(kan_domain),
                      zeros((1,2,3)),ones((1,2)),zeros(1))
        kan_scale=max(float(np.std(residual)),1e-8)
        trained=Network((layer,)).fit_linear(x, (residual/kan_scale)[:,None],ridge=.5)
        kan_bytes,kan_sha=trained.research_snapshot()
        kan_train=trained.evaluate(x)[0][:,0]*kan_scale
    prototypes = hdc_bias = post_bias = None
    if research_hdc:
        spec=Spec("MAP",256)
        rng=np.random.default_rng(_SEED)
        symbols=rng.choice([-1.,1.],size=(2,4,256)).astype(np.float32)
        codes=np.stack([_hdc_code(v,lo,hi,symbols,spec) for v in x])
        labels=(x[:,0]>float(np.median(x[:,0]))).astype(int)
        _need(set(labels.tolist())=={0,1}, "two train-only HDC regimes required")
        protos=np.stack([codes[labels==i].mean(axis=0) for i in (0,1)])
        # Actual existing HDC MAP associative matcher checks typed candidates.
        Cleanup(spec,protos)
        prototypes=tuple(tuple(float(v) for v in row) for row in protos)
        hdc_bias=tuple(float(np.mean(residual[labels==i])) for i in (0,1))
        post_bias=tuple(float(np.mean((residual-kan_train)[labels==i])) for i in (0,1))
    m=Fitted(series.identity,series.provenance.raw_sha256,
             horizon_ms,lag_ms,split.train_until_ms,
             _hash(tuple((r.origin_ms,r.target_ms,r.feature_values,r.target)
                         for r in train.examples)),
             scaler,tuple(float(z) for z in ridge[0]),
             tuple(float(z) for z in ridge[1]),
             tuple(float(z) for z in ridge[2]),float(tau),float(scaler.mean),
             research_kan,research_hdc,kan_bytes,kan_sha,kan_domain,
             float(kan_scale),prototypes,hdc_bias,post_bias,
             float(correction_cap),"")
    return replace(m,identity=_hash(_model_material(m)))


def _predict(model, batch):
    x,_=_xy(batch)
    ridge=(np.asarray(model.ridge_mean),np.asarray(model.ridge_scale),
           np.asarray(model.ridge_weight))
    origin=model.scaler.mean+model.scaler.standard_deviation*x[:,0]
    future = model.ssm_train_mean+ssm_zoh_rate(
        model.ssm_tau_seconds,model.horizon_ms/1000.)*(
            origin-model.ssm_train_mean)
    outputs={
        "persistence":origin.copy(),
        "train_mean":np.full(len(x),model.ssm_train_mean,dtype=float),
        "direct_ridge":ridge_predict(ridge,np.column_stack((x,np.ones(len(x))))),
        "timeaware_ssm":future,
    }
    counters={"kan_ood":0,"hdc_ood":0,"hdc_abstained":0,"hdc_accepted":0}
    kan=np.zeros(len(x))
    if model.research_kan or model.research_hdc:
        limits=np.asarray(model.kan_domain,dtype=float)
        lo=limits[:,0];hi=limits[:,1]
        inside=np.all((x>=lo)&(x<=hi),axis=1)
    if model.research_kan:
        trained=load_snapshot(model.kan_snapshot,model.kan_snapshot_sha256)
        if inside.any():
            kan[inside]=trained.evaluate(x[inside])[0][:,0]*model.kan_residual_scale
        kan=np.clip(kan,-model.correction_cap,model.correction_cap)
        counters["kan_ood"]=int((~inside).sum())
        outputs["ssm_kan"]=future+kan
    if model.research_hdc:
        spec=Spec("MAP",256)
        rng=np.random.default_rng(_SEED)
        symbols=rng.choice([-1.,1.],size=(2,4,256)).astype(np.float32)
        bank=Cleanup(spec,np.asarray(model.hdc_prototypes,dtype=np.float32))
        hdc=np.zeros(len(x));combined=np.zeros(len(x))
        for i,row in enumerate(x):
            if not inside[i]:
                counters["hdc_ood"]+=1
                counters["hdc_abstained"]+=1
                continue
            candidate=bank.propose(_hdc_code(row,lo,hi,symbols,spec),
                                   minimum=.12,margin=.01)
            if candidate is None:
                counters["hdc_abstained"]+=1
                continue
            counters["hdc_accepted"]+=1
            hdc[i]=model.hdc_bias[candidate.index]
            combined[i]=model.hdc_post_kan_bias[candidate.index]
        outputs["ssm_hdc"]=future+np.clip(hdc,-model.correction_cap,model.correction_cap)
        if model.research_kan:
            outputs["ssm_kan_hdc"]=future+np.clip(
                kan+combined,-model.correction_cap,model.correction_cap)
    for name,arr in outputs.items():
        _need(np.isfinite(arr).all() and len(arr)==len(x)
              and np.max(np.abs(arr))<=1e12,
              "nonfinite/out-of-bounds forecast: "+name)
    return outputs,counters


def _metric(truth,pred):
    _need(len(truth)==len(pred) and len(truth)>0
          and np.isfinite(truth).all() and np.isfinite(pred).all(),
          "finite matched forecast scores required")
    e=truth-pred
    return Score(len(truth),float(np.mean(np.abs(e))),
                 float(sqrt(np.mean(e*e))))


def _cal_internal(series, model):
    # NEVER request the test fold at calibration time.
    names=("statistical.ridge","research.ssm")+(
        ("research.kan",) if model.research_kan else ())+(
        ("research.hdc",) if model.research_hdc else ())
    batch=_matched(series,model.scaler,"cal",model.horizon_ms,
                   model.lag_ms,names)
    pred,_=_predict(model,batch)
    _,truth=_xy(batch)
    scores=tuple((name,_metric(truth,pred[name])) for name in model.methods)
    # The tie order is frozen by METHODS; no test-label choice is possible here.
    selected=min(scores,key=lambda a:(a[1].mae,model.methods.index(a[0])))[0]
    cal=Calibration(model.identity,series.identity,model.methods,scores,
                    selected,_hash(tuple((r.origin_ms,r.target_ms)
                                         for r in batch.examples)))
    return cal,batch,pred


def calibrate(series: data.QualifiedSeries, model: Fitted) -> Calibration:
    _fit_check(model,series)
    return _cal_internal(series,model)[0]


def _blocks(values,times,step,block_size):
    """Nonoverlapping uninterrupted clock runs; never connect unknown gaps."""
    _need(len(values)==len(times) and block_size>=2,"block arguments")
    if step is None or not len(times):
        return np.empty((0,block_size),dtype=float)
    breaks=np.r_[0,np.flatnonzero(np.diff(times)!=step)+1,len(times)]
    groups=[values[left+i:left+i+block_size]
            for left,right in zip(breaks[:-1],breaks[1:])
            for i in range(0,right-left-block_size+1,block_size)]
    return np.asarray(groups,dtype=float) if groups else np.empty((0,block_size))


def _interval(ycal,calpred,tcal,ytest,testpred,ttest,step,block_size):
    c=_blocks(np.abs(ycal-calpred),tcal,step,block_size)
    t=_blocks(np.abs(ytest-testpred),ttest,step,block_size)
    if len(c)<9 or len(t)<5:
        return IntervalAudit("REFUSED_INSUFFICIENT_DEPENDENT_BLOCKS",.90,
                             len(c),len(t),None,None,None)
    rank=ceil((len(c)+1)*.9)-1
    if rank>=len(c):
        return IntervalAudit("REFUSED_FINITE_RANK",.9,len(c),len(t),None,None,None)
    radius=float(np.sort(c.max(axis=1))[rank])
    hit=np.abs(ytest-testpred)<=radius
    return IntervalAudit("DESCRIPTIVE_BLOCK_MAX_ONLY",.9,
                         len(c),len(t),radius,float(np.mean(hit)),
                         float(np.mean(t.max(axis=1)<=radius)))


def _bootstrap(truth,reference,selected,times,step,block_size):
    difference=np.abs(truth-reference)-np.abs(truth-selected)
    blocks=_blocks(difference,times,step,block_size)
    if len(blocks)<9:
        return DependenceAudit("REFUSED_INSUFFICIENT_PAIRED_BLOCKS",
                               len(blocks),float(np.mean(difference)),None)
    rng=np.random.default_rng(5506)
    means=np.asarray([float(np.mean(blocks[
        rng.integers(0,len(blocks),len(blocks))])) for _ in range(256)])
    return DependenceAudit("DESCRIPTIVE_NONOVERLAP_BLOCK_BOOTSTRAP",
                           len(blocks),float(np.mean(difference)),
                           (float(np.quantile(means,.025)),
                            float(np.quantile(means,.975))))


def evaluate_holdout(series: data.QualifiedSeries, model: Fitted,
                     calibration: Calibration, *,
                     block_size: int = 4) -> Evaluation:
    """Scoring only; method selected before test is materialized.

    The calibration object is exactly rederived from the trusted frozen
    training source/parameters: it cannot be exchanged with a test winner.
    """
    _fit_check(model,series)
    _need(type(block_size) is int and 2<=block_size<=32,
          "bounded fixed dependence-block width")
    expected,cal_batch,cal_pred=_cal_internal(series,model)
    _need(type(calibration) is Calibration and calibration==expected
          and calibration.selected_on=="cal"
          and calibration.execution_authorized is False,
          "forged or post-hoc-selected calibration refused")
    names=("statistical.ridge","research.ssm")+(
        ("research.kan",) if model.research_kan else ())+(
        ("research.hdc",) if model.research_hdc else ())
    test=_matched(series,model.scaler,"test",model.horizon_ms,
                  model.lag_ms,names)
    pred,counts=_predict(model,test)
    _,yt=_xy(test)
    _,yc=_xy(cal_batch)
    scores=tuple((name,_metric(yt,pred[name])) for name in model.methods)
    observed=dict(scores); chosen=calibration.selected
    caltimes=np.asarray([r.origin_ms for r in cal_batch.examples],dtype=np.int64)
    testtimes=np.asarray([r.origin_ms for r in test.examples],dtype=np.int64)
    step=series.clock.nominal_interval_ms
    interval=_interval(yc,cal_pred[chosen],caltimes,
                       yt,pred[chosen],testtimes,step,block_size)
    ridge_interval=_interval(yc,cal_pred["direct_ridge"],caltimes,
                             yt,pred["direct_ridge"],testtimes,step,block_size)
    paired=_bootstrap(yt,pred["direct_ridge"],pred[chosen],
                      testtimes,step,block_size)
    return Evaluation(
        series.identity,model.identity,calibration,
        _hash(tuple((r.origin_ms,r.target_ms) for r in test.examples)),
        scores,observed["direct_ridge"].rmse-observed[chosen].rmse,
        observed["direct_ridge"].mae-observed[chosen].mae,
        interval,ridge_interval,paired,
        tuple(sorted(counts.items())),test.eligible_origins,test.skipped)


def run_offline(raw: bytes, *, site_id: str, units: data.Units,
                clock: data.Clock, provenance: data.Provenance,
                horizon_ms: int, lag_ms: int,
                research_kan: bool = False, research_hdc: bool = False,
                block_size: int = 4) -> Evaluation:
    """Trusted *offline research* convenience: no filesystem, network or grants.

    Test score is evaluated after training/calibration. This is not the final
    pre-registered independent Orc-graph-vs-ridge benchmark.
    """
    series=data.qualify(raw,site_id=site_id,units=units,clock=clock,
                        provenance=provenance)
    model=fit_train(series,horizon_ms=horizon_ms,lag_ms=lag_ms,
                    research_kan=research_kan,research_hdc=research_hdc)
    selected=calibrate(series,model)
    return evaluate_holdout(series,model,selected,block_size=block_size)
