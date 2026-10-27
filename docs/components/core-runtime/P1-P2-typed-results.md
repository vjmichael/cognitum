# C01 — Typed Cognitive Capability Result Contract v1

**Defined:** 2026-10-26  
**Implementation branch:** `cognitum/c01-typed-results-v1` (Cognitum only)  
**Status:** P1 implementation and regression verification in progress; **not** an approved or compiled Lu Protobuf ABI  
**Applicable modules:** C05 exact calculator; proposed future C08 HDC retrieval, C09 KAN numerical estimates and C10+ domain-specific successors  
**Authority:** [Cognitum-only Lu DLC Core Extension addenda](../../lu-dlc-ce-addenda.md) · [Lu-host integration design](../../lu-cognitum-integration.md)

## 1. The two independent questions

1. **Execution status:** `completed`, `validated`, `invalid_input`, `unavailable`, `denied`, `timed_out`, `error`. Only `completed` can have a computed value. `validated` means *policy/schema checks only; nothing ran*. A timeout, refusal, disabled extension or failed worker cannot carry an exact or heuristic result.
2. **Knowledge/result claim:** a successful execution yields an explicitly discriminated value type: `exact_rational`, `numerical_estimate`, or `retrieved_references`. Its **assurance is derived from the value kind**, not written by the requesting model. No generic `{"ok":true,"value":anything}` or free-form assurance string is accepted.

The loaded transformer still decides how to interpret tool results inside Lu, subject to Lu policy. Cognitum never changes model weights or grants permissions.

## 2. Typed variants

| Variant | Fields / bounded semantics | Assurance and mandatory limitations |
|---|---|---|
| `ExactRational` | Canonical reduced `Fraction` string, e.g. `1/2`, bounded to 1024 chars and 1024-bit numerator/denominator, no invalid or zero denominator | `exact_arithmetic`; `intent_not_verified` explicitly says exactness applies to the formal expression, **not** proof that the LLM formulated the user's intent correctly |
| `NumericalEstimate` | Finite decimal string + named `method`; optional *paired* ordered lower/upper bounds containing the point estimate; no implicit NaN/Infinity/coercion | `numerical`; requires `uncertainty_unquantified` if unbounded, or `bounds_not_probabilistic` if bounds provided. Bounds are **not** a calibrated probability/confidence interval; `intent_not_verified` also required |
| `RetrievedReferences` | 1–64 distinct opaque candidate IDs; source snapshot ID and the **same** indexed source snapshot ID required to detect obviously stale derived indexes | `heuristic`; always `retrieval_not_truth` and `no_permission_conferred`. Snapshot equality is not evidence of authorization, provenance quality or a canonical fact. Zero-result retrieval is not supported as a successful populated candidate set; future explicit empty/abstain result needs its own contract |
| `CapabilityFailure` | Sanitized, fixed category `code`, strict boolean `retryable` | No value or evidence; `no_computed_answer`; error code must match its execution-status category, denial/invalid input are nonretryable |
| `validated` | No value, no failure, no evidence | Mandatory `not_executed` disclosure |

`EvidenceRef` is an opaque bounded reference with a closed `kind`: `computation`, `source_snapshot` or `checkpoint`. It contains no raw source excerpt, prompt or grant. Every `completed` result must contain evidence; this is **structural validation**, not cryptographic attestation of the claim.

## 3. Closed JSON representation (Cognitum-side only)

Sample exact rational result, illustrative and **not** a Lu response:

```json
{
  "schema_version": "1.0.0",
  "request_id": "req1",
  "correlation_id": "turn1",
  "operation": "calc.rational",
  "operation_schema_version": "1.0.0",
  "status": "completed",
  "value": {"kind": "exact_rational", "value": "1/2"},
  "assurance": "exact_arithmetic",
  "interpretation": "assumption_bound",
  "failure": null,
  "evidence": [{"kind": "computation", "ref": "req1"}],
  "limitations": ["intent_not_verified"]
}
```

**Inbound `from_dict` and `from_json`** require exactly the documented top-level/nested keys; they reject unknown value types, wrong field types, duplicate JSON keys, spoofed assurance/interpretation, conflicting state/value/error combinations and result frames over **16 KiB**. No arbitrary `error.message` is accepted from untrusted input. Metadata IDs are opaque bounded ASCII tokens; the host must still ensure they do not contain secrets.

`RESULT_SCHEMA_VERSION` is separate from Cognitum's existing Python `CONTRACT_VERSION=1.3.0` and from Lu's experimental `CORE_CONTRACT_VERSION=1`; these versions are **not** interchangeable.

## 4. Backwards-compatible integration

[`cognitum/capability_results.py`](../../../cognitum/capability_results.py) implements immutable/frozen Python dataclasses, strict type/semantic validation, canonical JSON conversion and **`from_runtime_response`**.

The adapter deliberately:
- Converts **only** the existing `calc.rational` success with `assurance=exact_arithmetic`, outcome kind `value`, canonical exact result and known computation evidence. Its returned typed value is `ExactRational`, and it preserves the existing `Response.to_dict()` output unchanged.
- Converts ordinary `validated`, `unavailable`, `invalid_input`, `denied`, `timed_out` and `error` outcomes to a no-value envelope with fixed error categories.
- **Rejects unknown successful operations**, unverifiable assurance fields, forged evidence and contradictory non-success claims until their own reviewed domain adapters exist.
- Does not modify `cognitum/runtime.py`, `contracts.py`, `worker.py`, the existing calculator, golden manifest or replay format. No new runtime dependency is introduced.

This is an *opt-in* post-execution representation, **not** automatic model-visible tool output, a new execution path, or an authorized CE adapter.

## 5. Lu compatibility and separation

Read-only Lu source at `vjmichael/jan_alt` branch `lu/core-contracts-native-registry` has `lu.v1.ToolReply`, whose `oneof outcome` is either typed bytes `output` or `ToolError` (`code`, `message`, `retryable`). It also has a strict `ModelToolCodec` from Lu-owned model JSON to generated Protobuf payload and back.

**No Lu-side message changes are made here.** Any future Lu adapter must map an **approved Cognitum generated Protobuf domain result** into Lu's existing `ToolOutput`, map a real failure to the correct `ToolFailure`/host status, and keep provenance/limitations accessible to the model. The project must not put ad hoc JSON into `LegacyJsonArguments`, equate exact computations with verified user intent or claim that this Python JSON fixture is the official Lu Protobuf wire format. Requests for host-side changes or decisions remain **LU-CE-007**, and optional native CE lifecycle remains **LU-CE-001**.

## 6. P2 verification contract

[`tests/test_capability_results.py`](../../../tests/test_capability_results.py) exercises exact canonicalization and rejected rational formats; no numeric coercion/NaN/Infinity; bounded and ordered numerical bounds; stale and duplicated retrieval IDs; accepted failure categories/denials/timeout semantics; mandatory epistemic limitations and evidence; strict JSON roundtrips, unknown fields and duplicate keys; forged assurance; size limits; and adapter compatibility with actual existing `Runtime`/calculator.

**Test gate:** full `python -m unittest discover -s tests -p 'test_*.py' -v` plus `python -m cognitum --calculator replay evals/smoke.json` and `python -m compileall -q cognitum tests` on GitHub Actions Windows/Linux, Python 3.11 and 3.13. No test result is claimed until current-commit evidence is captured.

## 7. Known design limits and next component specialization

- Evidence-reference syntax prevents raw prose fields but **does not verify source authenticity**, nor does a hash or snapshot ID confer permission. C02 must enforce security, C06/C07 own canonical state and deletion/revision semantics.
- Retrieval only reports candidate IDs, without ranking scores or source claims. Future C08 P0 must compare actual HDC/FTS/dense recall and add scores only with explicit metric/unit calibration.
- KAN estimate bounds are arbitrary declared bounds; calibrated intervals, out-of-distribution behavior and estimator checkpoint lineage must be measured in C09, not invented by the envelope.
- Proof certificates, optimizer feasible/optimal/unknown, spatial graphs and simulation units deserve **new reviewed variant types**, not an uncontrolled generic `dict` or recycling `exact_arithmetic`.
- Payloads are optional local serialization and a future wire proposal; encrypted/authenticated transport, C02 worker isolation and Lu's actual generated messages are separate tasks.
- No HDC/KAN model was executed, no LLM benchmark was run, and no Lu files or settings were changed by this design.
