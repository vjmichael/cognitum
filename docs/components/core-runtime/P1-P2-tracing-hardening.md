# C01 — Tracing Schema Hardening (P1 maintenance / P2 focused smoke)

**Date:** 2026-10-26  
**Branch:** `cognitum/c01-tracing-guard`, based on `vjmichael/cognitum/main`.  
**Status:** **Prototype code committed, 9 isolated regression tests passed; full repository regression NOT YET EXECUTED**. Not a C01 P0 exit, P3 benchmark or security certification.  
**Scope:** Cognitum only; no Lu source, model, installer, system files, user AppData or archived HDC/KAN assets modified.

## Problem found

The existing `Trace` class declared that it retained metadata only, but its `append(event)` accepted **any Python dict**. It did not reject `payload`, `result`, `prompt`, arbitrary nested module metadata or unsanitized error strings. Another caller could accidentally persist sensitive content even when normal `Runtime._finish` only passed metadata. A durable audit record could also be confused with an in-memory entry on failed writes.

## Corrective implementation

In [`cognitum/tracing.py`](../../../cognitum/tracing.py) on the **feature branch**:
- Added `validated_event` with a **closed set of eight allowed trace keys**; refuses missing/extra fields and an unsupported `trace_version`.
- Accepts `module=None` (unavailable tool) or exactly `{"name","version"}` with bounded nonempty strings; rejects additional fields.
- Enforces a closed **allowlist** of currently defined runtime `execution_status` categories and sanitized `error` codes (including rejection of seemingly harmless but unregistered lowercase identifiers), and finite nonnegative numeric latency (rejects bool, NaN and Infinity).
- Creates an independent, normalized record before append; mutation of the original event or nested module can't retroactively alter the sink's memory.
- Serializes with `allow_nan=False` and only appends to `events` **after** the file write has succeeded. The previous **fail-closed, propagating error behavior** is preserved; no silent audit drop or false-completed call.
- Does **not** add external packages, network calls, schema migration or a new trace transport.

In [`tests/test_tracing.py`](../../../tests/test_tracing.py) added nine focused tests of accepted metadata, unexpected raw payload/result fields, nested secret fields, sanitizer allowlists, invalid statuses/fields, numeric bounds, defensive copies, unavailable module and disk error behavior.

**Important limitations:** this is an allowlist for field *names and types*, **not automatic de-identification** of allowed identifiers/module names. IDs must remain opaque and must not contain user data. A successfully returned buffered OS write is not a physical fsync guarantee; trace rotation, encryption, retention, process crash atomicity and long-running resource limits remain open. This prototype accepts only one trace format version and can require future schema migrations. Invalid metadata—including future status or error codes not explicitly added to the sink—causes failure rather than silently bypassing the audit sink. Keep this list in step with intentional runtime outcome categories.

## Test evidence — isolated copy of the committed source/test pair

A local directory containing the **same source and test text** as the branch changes was executed in Python 3.13.5 on Linux x86_64; the original Cognitum repository was not clonable in this test container. Results:

```text
python -m unittest discover -s tests -p 'test_tracing.py' -v
Ran 9 tests in 0.002s
OK

# With a temporary tests/__init__.py to exercise default discovery:
python -m unittest discover -v
Ran 9 tests in 0.002s
OK

python -m compileall -q cognitum/tracing.py tests/test_tracing.py
# passed
```

**P2 coverage limitation:** these nine tests run **against only the tracing module and its new test file**, not the full Cognitum install and not the Windows desktop. They exercise no worker spawn and do not establish end-to-end Lu/native CE compatibility.

**Before merging to `main`:**
1. Run **all existing Cognitum tests** with `python -m unittest discover -v` from a complete repository checkout, including `tests/test_core.py` and `tests/test_calculator.py`.
2. Confirm `Runtime._finish` events in normal, error, timeout, disabled and research paths are all within the strict schema.
3. Audit error codes used by new providers and ensure no unsanitized exceptions are passed to tracing. Keep the existing `manifest_v1.json` unchanged.
4. Test Windows UTF-8 file writes and non-writeable path failures; confirm fail-closed behavior is intentional and safely reported by the host rather than silently discarding audit evidence.
5. Decide on log rotation/durable auditing/error reporting in C02/C03 P0 design.

## Implementation status

**P1 targeted hardening implemented** on the isolated branch. **P2 focused smoke passed 9/9**, broader P2 regression is **blocked by checkout/runtime access to private repository**; P3 model and performance benchmarks not started. This is not approval to change Lu or activate optional untrusted providers.
