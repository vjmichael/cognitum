"""COG-05-SSM-POST-NATIVE-05: SHA-locked scientific *scope*, not law discovery."""
from __future__ import annotations
import hashlib
import json
import os
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINS = {
    "cognitum/research/ssm_independent_publishers.py": "ffbc2c0f14ec8f8e46c97ee2f1e0bfa9adeef7d7",
    "research_tests/ssm_postnative05/test_publishers.py": "adc71996bda0cfec0e01e580b981b236bd533d3b",
    "research_tests/ssm_postnative05/data/NOAA_RA_station_2025.csv": "8421af63a839c767555a53af74b71106ee68241e",
    "research_tests/ssm_postnative05/data/.gitattributes": "07826903c67f6eb9bd58aa2d84bf200a88659251",
    "research_tests/ssm_postnative05/data/USGS_NaturalFlow_1906_2015.csv": "2f986df07dce96b800829856e751b247e4179aaf",
}
EXPECTED = 15


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inventory(path):
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    require(suite is not None, "JUnit testsuite")
    return {k: int(suite.get(k, "0")) for k in ("tests", "failures", "errors", "skipped")}


def run(out_dir):
    from tools.ssm_postnative04.acceptance import PINS as PREVIOUS_NEW, PRIOR_SOURCE
    from cognitum.research import ssm_independent_publishers as s

    output = Path(out_dir).resolve()
    require(not output.exists(), "refuse to overwrite old receipts")
    head = git("rev-parse", "HEAD")
    require(not os.environ.get("GITHUB_SHA") or head == os.environ["GITHUB_SHA"], "workflow source SHA")
    require(not git("status", "--porcelain", "--untracked-files=no"), "tracked source dirty")
    for path, pin in {**PRIOR_SOURCE, **PREVIOUS_NEW, **PINS}.items():
        require(git("rev-parse", head + ":" + path) == pin, "source pin mismatch: " + path)
    output.mkdir(parents=True)
    trace = []
    for name, path in (
        ("noaa_partner_water_level", "research_tests/ssm_postnative05/data/NOAA_RA_station_2025.csv"),
        ("usgs_natural_flow", "research_tests/ssm_postnative05/data/USGS_NaturalFlow_1906_2015.csv"),
    ):
        raw = (ROOT / path).read_bytes()
        series = s.ingest(name, raw)
        report = s.evaluate(series)
        require(report["source_git_blob"] == PINS[path], "publisher SHA/ref mismatch")
        require(not report["execution_authorized"] and not report["physical_law_discovered"]
                and not report["conditional_coverage_guaranteed"]
                and not report["scientifically_qualified_hybrid_superiority"], "scientific overclaim")
        trace.append(report)
    science = output / "science.json"
    science.write_text(json.dumps(trace, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    test_xml = output / "tests.xml"
    process = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "research_tests/ssm_postnative05",
         "--junitxml", str(test_xml)],
        cwd=ROOT, capture_output=True, text=True, timeout=1200,
        encoding="utf-8", errors="replace")
    log = output / "tests.log"
    log.write_text(process.stdout + "\n" + process.stderr, encoding="utf-8")
    require(process.returncode == 0, "pytest failed (see tests.log)")
    actual = inventory(test_xml)
    require(actual == {"tests": EXPECTED, "failures": 0, "errors": 0, "skipped": 0},
            "test inventory drift " + repr(actual))

    receipt = {
        "task": "COG-05-SSM-POST-NATIVE-05",
        "status": "PASS_FOR_BOUND_PUBLISHER_DATA_BASELINES_ONLY",
        "source_sha": head, "platform": platform.platform(), "python": sys.version,
        "source_pins": PINS,
        "inherited_postnative04_pins": PREVIOUS_NEW,
        "inherited_postnative03_pins": PRIOR_SOURCE,
        "data_publishers": ["NOAA-CO-OPS", "DOI-USGS"],
        "independent_original_sensor_attestations_verified": False,
        "external_data_license_ambiguity_resolved": False,
        "scientifically_qualified_hdc_kan_ssm_superiority": False,
        "dependence_valid_coverage_guarantee": False,
        "physical_law_discovered": False,
        "execution_authorized": False,
        "tests": actual,
        "files_sha256": {p.name: sha(p.read_bytes()) for p in (science, test_xml, log)},
        "science_limit": "observational and derived source comparisons; fixed-step HDC/KAN/SSM excluded on these new sources",
        "preserved_postnative04_native_sha": "6160e322ba24f8ec4d8f4a7d90ad885daeb32c92",
    }
    (output / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
                                         encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "source_sha": head,
                      "tests": actual, "science_sha256": receipt["files_sha256"]["science.json"]}, sort_keys=True))


if __name__ == "__main__":
    require(len(sys.argv) == 2, "output directory required")
    run(sys.argv[1])
