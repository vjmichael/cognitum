"""ORCH-01B: scientific source custody, immutable time, leakage-safe feature gates."""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import math

import pytest

from cognitum.orc_science_data import (
    Units, Clock, Provenance, qualify, split_chronological,
    fit_train_scaler, CandidateContract, check_compatibility,
    prepare_forecasts, assert_matched_cohorts, MAX_ROWS, MAX_BYTES,
)
from cognitum.orc_graph import catalog

START = 1_700_000_000_000
STEP = 60_000
HEADER = "timestamp_ms,available_ms,value,observed,observation_id"


def data(n=40, *, missing=(), delayed=(), mutations=None, delete=()):
    changed = mutations or {}
    rows = []
    for i in range(n):
        if i in delete:
            continue
        time = START + i * STEP
        published = time + (2 * STEP if i in delayed else 0)
        value = f"{(i % 9) + i * 0.125:.6f}" if i not in missing else ""
        fields = [str(time), str(published), value, "0" if i in missing else "1", f"obs{i}"]
        fields = changed.get(i, fields)
        rows.append(",".join(fields))
    return (HEADER + "\n" + "\n".join(rows) + "\n").encode()


def source(raw, *, rights="unknown", unit_evidence="declared"):
    return Provenance("publisherX", "publisher:datasets/station1",
                      sha256(raw).hexdigest(), rights, unit_evidence)


def series(*, raw=None, units=None, clock=None, rights="unknown", unit_evidence="declared"):
    raw = data() if raw is None else raw
    return qualify(raw, site_id="station1",
                   units=units or Units("water_level", "m"),
                   clock=clock or Clock(nominal_interval_ms=STEP),
                   provenance=source(raw,rights=rights,unit_evidence=unit_evidence))


def contract(name="statistical.ridge", *, units=None, **kwargs):
    return CandidateContract(name, units or Units("water_level", "m"), **kwargs)


def batch(s=None, name="statistical.ridge", fold="test", **kwargs):
    s = s or series()
    split = split_chronological(s)
    scale = fit_train_scaler(s,split)
    return prepare_forecasts(s,split,scale,contract(name),fold=fold,
                             horizon_ms=kwargs.pop("horizon_ms",STEP),
                             lag_ms=kwargs.pop("lag_ms",STEP), **kwargs)


def test_custody_verified_original_bytes_and_immutable_rows():
    raw=data()
    s=series(raw=raw)
    assert s.provenance.raw_sha256 == sha256(raw).hexdigest()
    assert s.rows[0].timestamp_ms==START and s.rows[-1].timestamp_ms==START+39*STEP
    assert s.identity == series(raw=raw).identity
    assert not s.has_missing
    with pytest.raises(FrozenInstanceError):
        s.rows[0].value=999.0
    with pytest.raises(FrozenInstanceError):
        s.site_id="mutate"


@pytest.mark.parametrize("difference", [
    "raw_byte", "wrong_site", "unit", "publisher", "rights", "evidence",
])
def test_source_identity_binds_exact_bytes_and_metadata(difference):
    raw=data()
    a=series(raw=raw)
    if difference=="raw_byte": b=series(raw=data(mutations={39:[str(START+39*STEP),str(START+39*STEP),"888","1","obs39"]}))
    elif difference=="wrong_site":
        b=qualify(raw,site_id="station2",units=a.units,clock=a.clock,provenance=source(raw))
    elif difference=="unit":
        b=series(raw=raw,units=Units("temperature","K"))
    elif difference=="publisher":
        b=qualify(raw,site_id="station1",units=a.units,clock=a.clock,
                  provenance=replace(source(raw),publisher="anotherPublisher"))
    elif difference=="rights":
        b=series(raw=raw,rights="publisher_reported")
    else:
        b=series(raw=raw,unit_evidence="publisher_documented")
    assert a.identity != b.identity


def test_rejects_modified_upstream_bytes():
    raw=data()
    p=source(raw)
    with pytest.raises(ValueError,match="source content SHA256"):
        qualify(raw+b"extra",site_id="station1",units=Units("water_level","m"),
                clock=Clock(),provenance=p)


@pytest.mark.parametrize("raw",[
    b"", b"\xff"*50, b"unexpected\n"+b"x"*40,
    (HEADER+"\n").encode(),
])
def test_invalid_empty_malformed_and_short_sources(raw):
    with pytest.raises(ValueError):
        series(raw=raw)


@pytest.mark.parametrize("case",[
    "duplicate_time", "duplicate_id", "nonmonotonic", "missing_value",
    "imputation", "invalid_flag", "nan", "inf", "bad_millisecond",
    "available_before_time", "extra_column",
])
def test_adversarial_csv_rejections(case):
    raw=data()
    lines=raw.decode().splitlines()
    i=10
    fields=lines[i+1].split(",")
    if case=="duplicate_time": fields[0]=str(START+9*STEP)
    elif case=="duplicate_id": fields[4]="obs9"
    elif case=="nonmonotonic": fields[0]=str(START+5*STEP)
    elif case=="missing_value": fields[2]=""
    elif case=="imputation": fields[3]="0"
    elif case=="invalid_flag": fields[3]="yes"
    elif case=="nan": fields[2]="nan"
    elif case=="inf": fields[2]="inf"
    elif case=="bad_millisecond": fields[0]="1.7e12"
    elif case=="available_before_time": fields[1]=str(START+9*STEP)
    else: fields.append("host_exec")
    lines[i+1]=",".join(fields)
    with pytest.raises(ValueError):
        series(raw=("\n".join(lines)+"\n").encode())


@pytest.mark.parametrize("bad", [
    Units("water_level","m"),
    Units("discharge","m3/s"),
    Units("temperature","K"),
    Units("dimensionless","1"),
])
def test_valid_declared_unit_pairs(bad):
    assert bad.symbol


@pytest.mark.parametrize("kind,unit",[
    ("discharge","m"),("water_level","m3/s"),("temperature","degC"),
    ("dimensionless","m"),("unknown","m"),
])
def test_forbid_implicit_unit_conversion(kind,unit):
    with pytest.raises(ValueError):
        Units(kind,unit)


def test_missing_is_explicit_never_imputed():
    s=series(raw=data(missing=(5,9,34)))
    assert s.has_missing and s.rows[5].observed is False
    assert s.rows[5].value is None
    a=fit_train_scaler(s,split_chronological(s))
    assert a.count==22


def test_regular_clock_gap_refused_but_irregular_clock_preserved():
    raw=data(delete=(5,))
    with pytest.raises(ValueError,match="sampling gap"):
        series(raw=raw)
    s=series(raw=raw,clock=Clock(nominal_interval_ms=None))
    assert s.clock.nominal_interval_ms is None and len(s.rows)==39


def test_delayed_measurements_not_fitted_after_train_cutoff():
    s=series(raw=data(delayed=(23,)))
    p=split_chronological(s)
    fitted=fit_train_scaler(s,p)
    assert fitted.count==23 and p.train_until_ms==START+23*STEP


def test_chronological_split_is_strict_60_20_20():
    s=series()
    p=split_chronological(s)
    assert (p.train_stop,p.cal_stop,p.row_count)==(24,32,40)
    assert p.bounds("train")==(0,24) and p.bounds("cal")==(24,32)
    assert p.bounds("test")==(32,40)
    with pytest.raises(ValueError): p.bounds("validation")
    with pytest.raises(FrozenInstanceError): p.cal_stop=33


def test_train_only_fit_ignores_altered_test_values():
    a=series()
    raw=data(mutations={37:[str(START+37*STEP),str(START+37*STEP),"900000","1","obs37"]})
    b=series(raw=raw)
    fa=fit_train_scaler(a,split_chronological(a))
    fb=fit_train_scaler(b,split_chronological(b))
    assert fa.mean==fb.mean and fa.standard_deviation==fb.standard_deviation
    assert fa.training_rows_sha256==fb.training_rows_sha256
    assert fa.series_identity!=fb.series_identity


def test_scaler_rejects_other_source_and_arbitrary_altered_stats():
    s=series()
    p=split_chronological(s)
    sc=fit_train_scaler(s,p)
    with pytest.raises(ValueError,match="transformation"):
        prepare_forecasts(s,p,replace(sc,mean=sc.mean+1),contract(),
                          fold="test",horizon_ms=STEP,lag_ms=STEP)
    t=series(raw=data(missing=(39,)))
    with pytest.raises(ValueError,match="transformation"):
        prepare_forecasts(t,split_chronological(t),sc,contract(),
                          fold="test",horizon_ms=STEP,lag_ms=STEP)


@pytest.mark.parametrize("name", [
    "research.hdc","research.kan","research.ssm","statistical.ridge",
    "temporal.kalman","math.linear",
])
def test_first_class_candidate_compatibility_without_execution_grants(name):
    c=contract(name)
    status=check_compatibility(series(),c)
    assert status.compatible and status.reasons==()
    assert status.execution_authorized is False
    assert name in {x.operation for x in catalog()}


def test_quantity_mismatch_returns_explicit_refusal():
    c=CandidateContract("research.ssm",Units("discharge","m3/s"))
    result=check_compatibility(series(),c)
    assert not result.compatible
    assert "quantity_or_unit_mismatch_no_auto_conversion" in result.reasons


def test_regular_required_rejects_irregular_source():
    s=series(clock=Clock(nominal_interval_ms=None))
    result=check_compatibility(s,contract("research.ssm",sampling="regular_required"))
    assert not result.compatible
    assert result.reasons==("irregular_clock_unsupported",)


def test_missing_refusal_even_when_numerical_sample_exists():
    s=series(raw=data(missing=(2,)))
    result=check_compatibility(s,contract("research.kan",missing="complete_required"))
    assert not result.compatible
    assert result.reasons==("missing_measurements_unsupported",)


def test_units_evidence_cannot_be_silently_promoted():
    s=series()
    v=check_compatibility(s,contract(minimum_unit_evidence="publisher_documented"))
    assert not v.compatible
    assert v.reasons==("insufficient_reported_unit_evidence",)
    higher=series(unit_evidence="publisher_documented")
    assert check_compatibility(higher,contract(minimum_unit_evidence="publisher_documented")).compatible
    assert higher.provenance.unit_evidence=="publisher_documented"


@pytest.mark.parametrize("bad",["authenticated","sensor_attested","independent_verified"])
def test_no_unsupported_original_sensor_provenance_claim(bad):
    with pytest.raises(ValueError):
        source(data(),unit_evidence=bad)


def test_asof_forecast_targets_never_feature_inputs():
    s=series()
    p=split_chronological(s)
    scale=fit_train_scaler(s,p)
    out=prepare_forecasts(s,p,scale,contract(),fold="test",
                          horizon_ms=STEP,lag_ms=STEP)
    assert len(out.examples)==7 and out.eligible_origins==8
    assert out.skipped==( ("lag_unavailable",0),
                          ("origin_unavailable",0),
                          ("target_missing_or_outside_fold",1) )
    assert out.examples[0].origin_ms==START+32*STEP
    assert out.examples[0].target_ms==START+33*STEP
    assert out.examples[0].feature_values==(
        (s.rows[32].value-scale.mean)/scale.standard_deviation,
        (s.rows[31].value-scale.mean)/scale.standard_deviation)
    assert out.examples[0].target==s.rows[33].value


def test_delayed_observation_cannot_enter_origin_or_lag_features():
    s=series(raw=data(delayed=(33,)))
    p=split_chronological(s)
    sc=fit_train_scaler(s,p)
    out=prepare_forecasts(s,p,sc,contract(),fold="test",
                          horizon_ms=STEP,lag_ms=STEP)
    assert out.eligible_origins==8
    assert dict(out.skipped)["origin_unavailable"]>=1
    assert dict(out.skipped)["lag_unavailable"]>=1
    assert all(r.origin_ms!=START+33*STEP for r in out.examples)
    assert all(r.origin_ms!=START+34*STEP for r in out.examples)


def test_missing_target_is_dropped_with_reason_not_imputed():
    s=series(raw=data(missing=(33,)))
    b=batch(s)
    assert all(item.target_ms!=START+33*STEP for item in b.examples)
    assert dict(b.skipped)["target_missing_or_outside_fold"]>=2


def test_no_test_label_training_even_for_large_shift():
    s=series()
    changed=series(raw=data(mutations={33:[
        str(START+33*STEP),str(START+33*STEP),"90000","1","obs33"]}))
    a,b=batch(s),batch(changed)
    # Origin 32's available predictor remains identical while target changes.
    ra=next(r for r in a.examples if r.origin_ms==START+32*STEP)
    rb=next(r for r in b.examples if r.origin_ms==START+32*STEP)
    assert ra.feature_values==rb.feature_values
    assert ra.target!=rb.target


@pytest.mark.parametrize("fold",["train","cal","test"])
def test_all_folds_restrict_target_inside_same_fold(fold):
    s=series()
    p=split_chronological(s)
    result=batch(s,fold=fold)
    left,right=p.bounds(fold)
    admitted={row.timestamp_ms for row in s.rows[left:right]}
    assert result.examples
    assert all(row.origin_ms in admitted and row.target_ms in admitted
               for row in result.examples)


def test_matched_ridge_ssm_hdc_kan_candidate_cohorts():
    s=series()
    batches=[batch(s,name=n) for n in (
        "statistical.ridge","research.ssm","research.kan","research.hdc")]
    aligned=assert_matched_cohorts(*batches)
    assert len(aligned)==7
    assert all(not item.execution_authorized for item in batches)


def test_mismatched_horizon_refuses_silent_cohort_intersection():
    s=series()
    a=batch(s)
    b=batch(s,horizon_ms=2*STEP)
    with pytest.raises(ValueError,match="candidate cohorts differ"):
        assert_matched_cohorts(a,b)


def test_different_source_refuses_cross_source_cohort():
    a=batch(series())
    b=batch(series(raw=data(missing=(5,))))
    with pytest.raises(ValueError,match="candidate cohorts differ"):
        assert_matched_cohorts(a,b)


@pytest.mark.parametrize("bad",[
    {"horizon_ms":0},{"lag_ms":0},{"horizon_ms":True},{"lag_ms":1.0},
])
def test_exact_positive_time_lag_horizon_gate(bad):
    with pytest.raises(ValueError):
        batch(**bad)


def test_explicit_missing_and_delayed_data_keep_skip_denominator():
    s=series(raw=data(missing=(36,),delayed=(34,)))
    b=batch(s)
    assert b.eligible_origins==8
    assert sum(v for _,v in b.skipped)+len(b.examples)==8


def test_zero_variance_train_requires_refusal():
    raw=data(mutations={i:[str(START+i*STEP),str(START+i*STEP),"4","1",f"obs{i}"]
                        for i in range(24)})
    s=series(raw=raw)
    with pytest.raises(ValueError,match="constant"):
        fit_train_scaler(s,split_chronological(s))


def test_unverified_permissions_never_claim_licensed_data():
    s=series(rights="publisher_reported")
    assert s.provenance.rights_status=="publisher_reported"
    with pytest.raises(ValueError,match="licensing"):
        series(raw=data(),rights="verified")


def test_bad_metadata_and_unreviewed_operation_fail_closed():
    with pytest.raises(ValueError): Clock("local_naive")
    with pytest.raises(ValueError): Clock(nominal_interval_ms=True)
    with pytest.raises(ValueError): CandidateContract("research.unknown",Units("water_level","m"))
    with pytest.raises(ValueError): contract(sampling="auto_resample")
    with pytest.raises(ValueError): contract(missing="fill_mean")
    with pytest.raises(ValueError): contract(minimum_unit_evidence="instrument_attested")


def test_no_network_filesystem_or_model_execution_apis():
    import cognitum.orc_science_data as pipeline
    assert not hasattr(pipeline,"execute")
    assert not hasattr(pipeline,"open_file")
    assert not hasattr(pipeline,"download")
    assert not hasattr(pipeline,"fit_model")
