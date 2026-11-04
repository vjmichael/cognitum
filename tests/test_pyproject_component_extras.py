"""Guard the additive, optional dependency manifest used by C01-C19 integration.

This is a source-contract check, not a substitute for real pip resolution or
Windows/Linux native component acceptance.
"""
from __future__ import annotations

import re
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Established extras from the baseline and unified specialist branches.
# New component dependencies must be added without dropping these contracts.
REQUIRED = {
    "proto": {"protobuf"},
    "security": {"protobuf", "cryptography"},
    "scientific": {"protobuf", "mpmath"},
    "research-hdc-kan": {"protobuf", "numpy"},
    "planning-graph": {"protobuf", "networkx"},
    "planning-validation": {"protobuf", "unified-planning"},
    "causal-stats": {"protobuf", "numpy", "scipy", "statsmodels"},
    "causal-dowhy": {"protobuf", "numpy", "pandas", "dowhy"},
    "causal-econml": {"protobuf", "numpy", "econml"},
    "causal-discovery": {"protobuf", "numpy", "causal-learn"},
    "causal-timeseries-gpl": {"protobuf", "numpy", "tigramite"},
    "formal-z3": {"protobuf", "z3-solver"},
    "formal-cvc5": {"protobuf", "cvc5"},
    "optimization-mip": {"protobuf", "numpy", "scipy"},
    "optimization-schedule": {"protobuf", "ortools"},
    "probability-stats": {"protobuf", "numpy", "scipy"},
    "spatial-core": {"protobuf", "numpy", "scipy"},
    "spatial-vision": {"protobuf", "numpy", "scipy", "opencv-python-headless", "pillow"},
    "physics-ode": {"protobuf", "numpy", "scipy"},
    "temporal-statespace": {"protobuf", "numpy", "scipy"},
    "temporal-learned": {"protobuf", "numpy", "scipy", "scikit-learn"},
    "adaptation-classical": {"protobuf", "numpy", "scipy", "scikit-learn"},
    "topology-rips": {"protobuf", "numpy", "scipy", "ripser", "persim", "scikit-learn"},
    "topology-verify": {"protobuf", "numpy", "scipy", "ripser", "persim", "scikit-learn", "gudhi"},
}

def normalize_requirement(value: str) -> str:
    """Return the PEP 503 normalized distribution name without version markers."""
    match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", value)
    if not match:
        raise ValueError(f"Invalid requirement: {value!r}")
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()

def check_manifest(content: bytes) -> list[str]:
    try:
        manifest = tomllib.loads(content.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        return [f"invalid pyproject.toml: {exc}"]
    project = manifest.get("project", {})
    errors = []
    if project.get("dependencies") != []:
        errors.append("base Cognitum core must remain dependency-free (no forced specialist extras)")
    extras = project.get("optional-dependencies", {})
    for group, packages in REQUIRED.items():
        requirements = extras.get(group)
        if not isinstance(requirements, list):
            errors.append(f"missing optional dependency group: {group}")
            continue
        try:
            names = {normalize_requirement(value) for value in requirements if isinstance(value, str)}
        except ValueError as exc:
            errors.append(f"{group}: {exc}")
            continue
        if len(names) != len(requirements):
            errors.append(f"{group}: duplicate or malformed requirement entries")
        missing = packages - names
        if missing:
            errors.append(f"{group}: dropped dependencies: {', '.join(sorted(missing))}")
    return errors

class ComponentManifestTests(unittest.TestCase):
    def test_combined_manifest_preserves_all_component_groups(self):
        self.assertEqual(check_manifest((ROOT / "pyproject.toml").read_bytes()), [])

    def test_removed_component_group_is_rejected(self):
        data = (ROOT / "pyproject.toml").read_bytes()
        self.assertIn(b"topology-verify = [", data)
        mutated = data.replace(b"topology-verify = [", b"obsolete-topology-verify = [", 1)
        self.assertTrue(any("topology-verify" in item for item in check_manifest(mutated)))

    def test_removed_component_dependency_is_rejected(self):
        data = (ROOT / "pyproject.toml").read_bytes()
        self.assertIn(b'"ortools>=9.12,<10"', data)
        mutated = data.replace(b'"ortools>=9.12,<10"', b'"protobuf>=6.31,<8"', 1)
        self.assertTrue(any("optimization-schedule" in item for item in check_manifest(mutated)))

    def test_duplicate_group_is_invalid_toml(self):
        data = (ROOT / "pyproject.toml").read_bytes()
        mutated = data + b'\n[project.optional-dependencies]\nproto = ["protobuf"]\n'
        self.assertTrue(check_manifest(mutated))

if __name__ == "__main__":
    unittest.main()
