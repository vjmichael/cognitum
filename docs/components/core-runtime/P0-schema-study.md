# C01 / P0 — Python Schema Validator Comparison

**Experiment date:** 2026-10-26  
**Status:** Completed **illustrative research probe**, **not** P3 production benchmark, library adoption, or authorization for release.  
**Executable source:** [`research/schema_validation_probe.py`](../../../research/schema_validation_probe.py)  
**Design context:** [C01 native Lu audit](P0-lu-native-audit.md) · [P0 research](P0-research.md)

## Question and method

Cognitum's Python `Shape` currently supports only flat closed objects of bounded nonempty strings. Stateful memory and future composition require nested objects, nullable/optional fields, exact integer and boolean types and fail-closed unknown keys. Compare two established Python approaches for this **Python-internal** validator problem:

- **`jsonschema` 4.26.0:** reusable `Draft202012Validator` over an explicit Draft 2020-12 strict schema.
- **Pydantic 2.13.5:** cached `BaseModel` classes with `strict=True`, `extra="forbid"`, and explicit field bounds.

`research/schema_validation_probe.py` encodes equivalent four-field nested event schemas and checks eight inputs: ordinary valid event, explicit JSON null, absent optional field, integer passed to boolean field, boolean passed to integer field, unknown top-level field, empty nested required string, and negative integer. It runs 200 warmup validations followed by 5 batches of 2,500 valid event validations using `perf_counter_ns` and takes the median across batches.

## Local measurement (illustrative)

| Environment | Observed value |
|---|---|
| OS / architecture | Linux / x86_64 |
| Python | 3.13.5 |
| `jsonschema` | 4.26.0 |
| Pydantic | 2.13.5 |
| Case outcome | Both validators agree on all 8 covered cases |
| `jsonschema` repeated warm validation | 22.647 microseconds per call (median of 5 batches of 2,500) |
| Pydantic repeated warm validation | 1.565 microseconds per call (median of 5 batches of 2,500) |

A prior exploratory run of the same equivalent cases measured **22.826 vs 1.695 microseconds**, respectively. The committed source was then executed as above and produced the main values. These are single-process CPU microbenchmarks without load, uncertainty intervals, controlled CPU frequency, multiple host machines, dependency installation cost, memory measurements or a loaded transformer. Do not extrapolate throughput ratios to end-to-end Lu or Windows performance.

To reproduce in an isolated optional development environment:

```powershell
python -m pip install "jsonschema>=4" "pydantic>=2"
python research/schema_validation_probe.py
```

Do not add these packages to `pyproject.toml` production runtime dependencies solely because this probe exists. Review dependency integrity, licenses and pinned versions before any adoption.

## Design implication

1. **The Lu host already has a strict Rust `ModelToolCatalog` and `ModelToolCodec` path** converting model JSON directly into generated typed Protobuf. No Python JSON validator is required on that existing host boundary. Do not reimplement it.
2. Cognitum's existing trusted **calculator** can retain the compact standard-library `Shape`; a richer Python schema framework is not justified for that operation alone.
3. For Python-only **memory/state/research workers**, Pydantic v2 is a plausible candidate when nested typed models need repeated validation. Choose based on license/security/dependency compatibility, documented conversion semantics, Windows CPU measurements and an explicit comparison to a purpose-built typed dataclass validator. `jsonschema` may still be useful to validate published cross-language schemas/fixtures.
4. Distinguish **missing**, **explicit null**, **false**, **zero**, and **empty** at every JSON↔Protobuf boundary. This experiment checks acceptance of omitted/null values but **does not** prove that business-level presence state survives serialization; separate roundtrip fixtures are mandatory.
5. Neither library constitutes an OS security sandbox, source authentication, runtime permission control or proof that a transformer's natural-language tool formulation is correct.

**Decision:** no new production dependency; keep C01 P0 **in progress**, and target a focused typed-schema interoperability fixture before an adapter. Continue C02/C04 authorization/CE lifecycle design first.

**Source standards:** https://json-schema.org/draft/2020-12 ; https://protobuf.dev/programming-guides/field_presence/ .
