"""Optional P0 study: strict nested JSON Schema vs Pydantic validation.

Dependencies: jsonschema>=4 and pydantic>=2 (not Cognitum runtime deps).
Benchmark results are environment-specific, not a production promotion claim.
Run: python research/schema_validation_probe.py
"""
from __future__ import annotations

from importlib import metadata
from platform import machine, system
from statistics import median
from time import perf_counter_ns
import sys

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Attributes(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    source: str = Field(min_length=1)
    note: str | None = None


class Event(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    event_id: str = Field(min_length=1, max_length=64)
    revision: int = Field(ge=0)
    active: bool
    attributes: Attributes


SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object", "additionalProperties": False,
    "required": ["event_id", "revision", "active", "attributes"],
    "properties": {
        "event_id": {"type": "string", "minLength": 1, "maxLength": 64},
        "revision": {"type": "integer", "minimum": 0},
        "active": {"type": "boolean"},
        "attributes": {
            "type": "object", "additionalProperties": False,
            "required": ["source"],
            "properties": {
                "source": {"type": "string", "minLength": 1},
                "note": {"type": ["null", "string"]},
            },
        },
    },
}


def main() -> None:
    validator = Draft202012Validator(SCHEMA)
    base = {"event_id": "e_1", "revision": 0, "active": False,
            "attributes": {"source": "user"}}
    cases = {
        "valid": base,
        "explicit_null": {**base, "attributes": {"source": "user", "note": None}},
        "absent_optional": base,
        "wrong_boolean": {**base, "active": 0},
        "bool_as_integer": {**base, "revision": True},
        "unknown_field": {**base, "unexpected": "x"},
        "empty_source": {**base, "attributes": {"source": ""}},
        "negative_revision": {**base, "revision": -1},
    }
    for label, value in cases.items():
        schema_valid = validator.is_valid(value)
        try:
            Event.model_validate(value)
            model_valid = True
        except ValidationError:
            model_valid = False
        print(label, schema_valid, model_valid)
        assert schema_valid == model_valid, label

    print("Python", sys.version.split()[0], system(), machine())
    for package in ("jsonschema", "pydantic"):
        print(package, metadata.version(package))
    for label, fn in (
        ("jsonschema", lambda: validator.validate(base)),
        ("pydantic", lambda: Event.model_validate(base)),
    ):
        for _ in range(200):
            fn()
        samples = []
        for _ in range(5):
            start = perf_counter_ns()
            for _ in range(2500):
                fn()
            samples.append((perf_counter_ns() - start) / 2500 / 1000)
        print(label, "median_us_per_validation", round(median(samples), 3))


if __name__ == "__main__":
    main()
