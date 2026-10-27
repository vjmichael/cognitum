# C01 — Tracing Schema Hardening (P1 maintenance / P2 focused smoke)

**Date:** 2026-10-26  
**Branch:** `cognitum/c01-tracing-guard`, based on `vjmichael/cognitum/main`.  
**Status:** **P1 tracing patch committed; P2 complete repository regression PASSED on Linux/Windows Python 3.11/3.13 (40 unit tests and 12/12 synthetic replay per job).** Merged into Cognitum `main` by [PR #1](https://github.com/vjmichael/cognitum/pull/1); not P3 or Lu integration. Not a C01 P0 exit, P3 benchmark or security certification.  
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

## Complete real-checkout GitHub Actions evidence (additional, 2026-10-27 UTC)

[**Run 40444297105**](https://github.com/vjmichael/cognitum/actions/runs/40444297105) used `vjmichael/cognitum` at commit `0add94157cfb6be6c1d83784c1ea4d334fb18c76`, adding a four-platform Python CI workflow. All **four jobs passed**:

| Host | Python | Unit suite | Synthetic replay | Source compile |
|---|---|---:|---:|---|
| Linux (ubuntu-latest) | 3.11 | **40/40** | **12/12** | Pass |
| Linux (ubuntu-latest) | 3.13 | **40/40** | **12/12** | Pass |
| Windows (windows-latest) | 3.11 | **40/40** | **12/12** | Pass |
| Windows (windows-latest) | 3.13 | **40/40** | **12/12** | Pass |

**40 = 31 inherited tests + 9 new tracing tests.** These are normal GitHub runner environments, not the user's Windows desktop/AMD GPU. Review and host-security work remain necessary, but the former **full-regression blocker is cleared** for this isolated patch.


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

**Post-merge follow-up and ongoing safety review:**
1. **Completed on Linux and Windows CI:** all existing and new Cognitum tests pass on a complete GitHub checkout. Retain this full regression gate for any subsequent changes.
2. Confirm `Runtime._finish` events in normal, error, timeout, disabled and research paths are all within the strict schema.
3. Audit error codes used by new providers and ensure no unsanitized exceptions are passed to tracing. Keep the existing `manifest_v1.json` unchanged.
4. **Basic Windows CI success achieved**, including non-writeable path error fixture; further real-desktop Tauri integration and durable audit recording remain open.
5. Decide on log rotation/durable auditing/error reporting in C02/C03 P0 design.

## Implementation status

**P1 targeted hardening merged** into Cognitum `main`; **P2 focused smoke passed 9/9 and complete-repository Windows/Linux CI passed 40/40 per job, replay 12/12 per job**. The [combined main regression](https://github.com/vjmichael/cognitum/actions/runs/40444933715) also passed 51/51 units and 12/12 replay per job after PR #2 merged. Ongoing safety review remains; P3 model/performance benchmarks not started. This is not approval to change Lu or activate optional untrusted providers.
