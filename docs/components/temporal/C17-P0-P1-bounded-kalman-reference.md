# C17 P0/P1 — Bounded temporal reference augmentation

**Status:** First functional offline reference; **not** a complete C17 learned-SSM implementation or a Lu-host-registered capability.

**Transformer gap addressed:** A transformer can narrate irregular time series while overlooking chronological order, missing measurements, uncertainty growth, and whether a result was observed or extrapolated. C17 supplies an exact *typed time-series contract* plus a reproducible mathematical reference that a future Lu-authorized model could call.

## Initial capability

- Input: canonical, bounded Protobuf \`cognitum.temporal.v1.FilterRequest\` containing a scalar prior, per-second process variance, measurement variance, source-bound timestamped samples, optional observation presence, forecast horizon, and declared measurement units.
- Operation: deterministic CPU decimal arithmetic, scalar Kalman random-walk model with Joseph-form covariance update, including prediction-only steps for missing observations.
- Output: \`FilterResult\` with posterior mean, variance, accepted/missing counts, model name and mandatory limitation statements.
- Scope: 1–128 samples, fixed finite decimal grammar, maximum 7-day timeline, 1-day intersample gap, 1-hour forecast. These are arbitrary bounded reference constraints, not physically derived envelopes.
- Reject: invalid/nonfinite values, negative variances, zero observation noise, stale/reordered times, duplicate sources, oversized frames, malformed/noncanonical Protobuf and absent actual observations.

The \`source_id\` is a locator, not an authorization token. Declared units are syntactically checked, **not** dimensionally verified. This filter does not alter transformer weights, store canonical state, read conversations, or grant itself execution privileges.

## Testing

A 26-test unit suite includes analytical reference values, an independent \`fractions.Fraction\` cross-check, missing-data propagation, deterministic replay, strict Protobuf parsing, bounded-resource rejection and false-assurance guardrails. The initial local run on Python 3.13 passed **26 tests** (with 10 subtests).

## Why this fits augmentation first

A classical Kalman filter may be more appropriate than a novel learned model for this restricted case. Cognitum's contribution is providing a formal, model-understandable temporal operation with explicit uncertainty and provenance constraints. Novel SSMs remain optional future experiments, never required to beat the classical reference simply to justify access to that reference.

## Remaining C17 steps

- **P1.1:** Host-issued source provenance, unit dimensions and schema registration; keep first-party default-off.
- **P1.2:** Bounded typed multivariate system dynamics or a reproducible learned sequence-model adapter with checkpoint validation and OOD refusal.
- **P2:** Windows/Linux negative tests, cancellation and resource enforcement in a real Cognitum worker; reference numerical conditioning and drift.
- **P3:** Held-out temporal tasks: matched selected transformer with and without augmentation, conventional baselines, uncertainty and cost. No superiority or memory correctness claims without evidence.

**Lu remains read-only.** This branch is standalone Cognitum research and cannot authorize CE installation or bypass the host worker-security gate.
