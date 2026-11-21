"""Independent publisher provenance, real time gaps, and falsification gates."""
from pathlib import Path
import numpy as np
import pytest

from cognitum.research import ssm_independent_publishers as m

HERE = Path(__file__).parent / "data"
FILES = {
    "noaa_partner_water_level": "NOAA_RA_station_2025.csv",
    "usgs_natural_flow": "USGS_NaturalFlow_1906_2015.csv",
}


@pytest.fixture(scope="module", params=list(FILES))
def real_series(request):
    name = request.param
    return m.ingest(name, (HERE / FILES[name]).read_bytes())


def test_two_independent_publisher_organizations_are_preserved():
    assert {v["publisher"] for v in m.SOURCES.values()} == {"NOAA-CO-OPS", "DOI-USGS"}
    assert m.SOURCES["noaa_partner_water_level"]["origin"].startswith("RA partner")
    assert m.SOURCES["usgs_natural_flow"]["origin"].startswith("Colorado River reconstructed")


def test_original_upstream_bytes_are_unchanged(real_series):
    raw = (HERE / FILES[real_series["name"]]).read_bytes()
    assert m.git_blob(raw) == real_series["source_git_blob"]
    assert real_series["admitted_observations"] > 100
    assert np.isfinite(real_series["values"]).all()
    assert np.all(np.diff(real_series["times"]) > 0)
    assert not np.shares_memory(real_series["values"], real_series["times"])


def test_noaa_conflicting_timestamps_are_excluded_not_averaged():
    s = m.ingest("noaa_partner_water_level", (HERE / FILES["noaa_partner_water_level"]).read_bytes())
    assert s["original_records"] == 34099
    assert s["quarantined_conflicting_instants"] == 9
    assert s["quarantined_rows"] == 18
    assert s["irregular_intervals"] > 100
    assert s["observations"] == 34081


def test_usgs_separate_reconstructed_annual_flow_is_not_a_raw_gauge():
    s = m.ingest("usgs_natural_flow", (HERE / FILES["usgs_natural_flow"]).read_bytes())
    assert s["original_records"] == 110
    assert s["irregular_intervals"] == 0
    assert s["times"][0] == 1906 and s["times"][-1] == 2015
    assert "reconstructed" in m.SOURCES[s["name"]]["origin"]


@pytest.mark.parametrize("name", list(FILES))
def test_source_mutation_and_cross_source_swap_refused(name):
    raw = bytearray((HERE / FILES[name]).read_bytes())
    raw[100] = raw[100] ^ 1
    with pytest.raises(ValueError, match="byte identity"):
        m.ingest(name, bytes(raw))
    other = next(k for k in FILES if k != name)
    with pytest.raises(ValueError, match="byte identity"):
        m.ingest(name, (HERE / FILES[other]).read_bytes())


@pytest.mark.parametrize("name", list(FILES))
def test_chronological_folds_never_share_forecast_targets(name):
    s = m.ingest(name, (HERE / FILES[name]).read_bytes())
    previous = set()
    for horizon in m.SOURCES[name]["horizons"]:
        for start, stop in m.regions(s["observations"]):
            origin, target = m.origin_pairs(s, start, stop, horizon)
            assert len(origin) == len(target) and len(origin) > 10
            assert len(origin) and np.all(target > origin)
            assert np.all(origin >= start) and np.all(target < stop)
            assert np.all(s["times"][target] - s["times"][origin] == horizon)
            assert not set(target).intersection(previous)
            previous.update(target.tolist())
        previous.clear()


def test_no_future_values_in_origin_features_or_train_only_ridge():
    s = m.ingest("noaa_partner_water_level", (HERE / FILES["noaa_partner_water_level"]).read_bytes())
    folds = m.regions(s["observations"])
    tr, zt = m.origin_pairs(s, *folds[0], horizon=1800)
    te, ze = m.origin_pairs(s, *folds[2], horizon=1800)
    x_train = m.features(s, tr, 1800)
    a = m.ridge_fit(x_train, s["values"][zt])
    x_test = m.features(s, te[:50], 1800)
    p = m.ridge_forecast(a, x_test)
    mutated = {**s, "values": s["values"].copy()}
    # Change ONLY targets that occur after the first 50 held-out forecast origins.
    end = int(te[49])
    mutated["values"][end + 1:] += 1234.0
    b = m.ridge_fit(m.features(mutated, tr, 1800), mutated["values"][zt])
    q = m.ridge_forecast(b, m.features(mutated, te[:50], 1800))
    np.testing.assert_allclose(p, q, rtol=0, atol=1e-10)


def test_contiguous_block_quantile_does_not_bridge_real_gaps():
    times = np.r_[np.arange(0, 480) * 300, (np.arange(480, 960) + 20) * 300]
    errs = np.ones(960)
    errs[::24] = 4.0
    blocks = m.consecutive_blocks(errs, times, 300, 24)
    assert blocks.shape == (40, 24)
    assert np.all(blocks.max(1) == 4.0)
    with pytest.raises(ValueError, match="ordered"):
        m.consecutive_blocks(errs, times[::-1], 300, 24)


def test_block_dependence_declines_guaranteed_coverage():
    c_times = np.arange(0, 1000) * 300
    t_times = np.arange(1200, 2200) * 300
    cal = np.full(1000, 1.0)
    test = np.full(1000, 1.0)
    out = m.block_diagnostics(cal, c_times, test, t_times, 300, 24)
    assert out["status"] == "DESCRIPTIVE_ONLY"
    assert out["empirical_origin_coverage"] == 1
    assert out["synthetic_plus_3radius_coverage"] == 0
    assert not out["distribution_free_coverage"]
    refused = m.block_diagnostics(cal[:50], c_times[:50], test[:50], t_times[:50], 300, 24)
    assert refused["status"] == "REFUSED_INSUFFICIENT_BLOCKS"


@pytest.mark.parametrize("name", list(FILES))
def test_real_publishers_falsification_without_claim_of_laws(name):
    s = m.ingest(name, (HERE / FILES[name]).read_bytes())
    result = m.evaluate(s)
    assert result["publisher"] == m.SOURCES[name]["publisher"]
    assert set(result["outcomes"]) == {str(x) for x in m.SOURCES[name]["horizons"]}
    assert not result["physical_law_discovered"]
    assert not result["conditionally_coverage_guaranteed"] if "conditionally_coverage_guaranteed" in result else True
    assert not result["conditional_coverage_guaranteed"]
    assert not result["scientifically_qualified_hybrid_superiority"]
    assert not result["execution_authorized"] and not result["missing_data_imputed"]
    for horizon, report in result["outcomes"].items():
        assert not report["chosen_using_test_targets"]
        assert report["train_origins"] > 30 and report["test_origins"] > 10
        assert "persistence" in report["test_metrics"] and "direct_ridge" in report["test_metrics"]
        assert all(np.isfinite(v["rmse"]) for v in report["test_metrics"].values())
        if report["missingness"].get("status") == "REFUSED_INSUFFICIENT_TEST_OBSERVATIONS":
            assert name == "usgs_natural_flow"
            assert report["missingness"]["test_origins"] <= 20
        else:
            assert report["missingness"]["outage_fraction"] > .1
            assert report["missingness"]["high_target_censored_fraction"] > .1
        assert not report["dependence_calibration"]["distribution_free_coverage"]
        assert report["calibration_selected_model"] in report["calibration_metrics"]
    if name.startswith("noaa"):
        assert result["hdc_kan_ssm_native_falsification"].startswith("REFUSED_IRREGULAR")
    else:
        assert result["hdc_kan_ssm_native_falsification"].startswith("REFUSED_INSUFFICIENT")


def test_irregular_timestamps_are_not_silently_treated_as_equal_time_steps():
    s = m.ingest("noaa_partner_water_level", (HERE / FILES["noaa_partner_water_level"]).read_bytes())
    ix = {int(t): i for i, t in enumerate(s["times"])}
    i = next(j for j in range(2, len(s["times"]) - 25)
             if int(s["times"][j] + 300) not in ix)
    # The next array position is not a physically valid +5-minute target.
    assert s["times"][i + 1] - s["times"][i] != 300
    fold = next((f for f in m.regions(s["observations"]) if f[0] <= i < f[1]), None)
    assert fold is not None
    o, z = m.origin_pairs(s, *fold, 300)
    assert i not in set(o.tolist())
    assert np.all(s["times"][z] - s["times"][o] == 300)
