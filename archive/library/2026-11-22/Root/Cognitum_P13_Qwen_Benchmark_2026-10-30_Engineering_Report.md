# Cognitum P13 — Harder Qwen benchmark engineering report

**Date:** 2026-10-30. **Status:** Source implemented, tests passed; new Qwen evaluation NOT RUN.

## Outcome

Following the October 30 P12 raw-receipt audit, implemented a fresh **84-question, 14-family** stress battery rather than repeating the 12-case P8 experiment. The Windows pilot uses 14 family-stratified questions x 2 repetitions = **28 model requests** plus 1 warmup. The full test has 84 x 2 = **168 measured requests** plus 2 warmups. Both require the operator to run LM Studio's local Qwen model and explicitly type RUN in a Windows launcher. Neither launcher was executed against the user's Qwen here.

## Improvements based on P8/P12 observations

1. **Separate answer correctness from action-label compliance.** Report mistaken answers, unwarranted answers when evidence is unknown, unnecessary abstentions, malformed output, and truncated generations distinctly. No label score is described as executed unsafe actions.
2. **Evidence ownership is a host responsibility.** Added a fail-closed `p13_fenced_reference.py` interface that only releases a canonical current-record value via an in-fence host publication callback; tombstone/revocation/missing evidence withholds. It has simulated tests but is NOT implemented in Lu and cannot authenticate native grants or the caller-provided host.
3. **Adversarial, diversified, reproducible cases.** Added 84 synthetic questions (14 families, seed 20261030) with exact generated or brute-force-verified gold, 146-row revision aggregation, belief/fact counterfactuals, inverse base rates, planning, distractor joins, tool schema traps and instruction-in-source attacks. Gold is never present in model prompt messages.
4. **Safer trial mechanics.** Explicit local-only endpoint; no proxies or redirects; no output overwrite; append-only raw journal; explicit capture consent; two-pass reverse sequencing; family-stratified pilot; bounded HTTP and completion size; raw receipt and independent regrader. Transport failures and output-limit truncations are classified rather than dropped. Trial identity, model quantization and weights remain operator-reported and unattested.
5. **Internal verification vs model performance.** The local mock client completed a 28-call **scripted** demonstration and independent regrading. This is strictly a harness validation, NOT real model trial data.

## Local test evidence

- Selected C08/C09 tests, P12 and P13 together: **229 passed** (Linux Python 3.13).
- Standalone P13 unit-test module: **10 passed**.
- Full pilot and full dry-runs: both `NOT_RUN_PREFLIGHT_ONLY`; zero calls.
- Independent regrader successfully regraded a deliberately labeled `FAKE_MODEL_NOT_QWEN` synthetic receipt (28/28). Not evidence of Qwen correctness.
- Source baseline: **942** files preserved byte-for-byte; **11** new, **1** modified, **0** deleted; **954** source files excluding new manifest.
- Full ZIP SHA-256: `1d7f97805d906d58edc498f3e3600acf7ea0cc37e6a7b9e418c85367f4697d44`.
- Changes-only ZIP SHA-256: `c7b7c091a38ca8230d565ccc330cde1b5c1c488fc7406d4e9231516b51265d46`.
- Golden case plan SHA-256: `aa33037e7f1554572d3394029b07190877a06c15ad0631a6e1e5722464124041`.

## Live deployment boundary

Real local Qwen 3.8 27B was **not available** from the execution container; the user must use their running local LM Studio server. Quantization, seed control and model identity must be collected as claims, not assumed to be cryptographically attested. The suite tests transformers generically, **not a Cognitum ON/OFF efficacy difference**. A genuine improvement trial requires a separate matched condition using actual C08/C09 first-party kernels, controlled inference parameters and authoritative, permission-scoped source data. No changes to Lu or GitHub were made.

See the protocol/Windows scripts in the ZIP for instructions. Upload only the test receipt and grading report if raw responses can be shared.
