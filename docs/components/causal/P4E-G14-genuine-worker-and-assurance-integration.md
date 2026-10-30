# Cognitum C14 P4E G14 — Genuine Worker and Research-Only Assurance Integration

**Date:** 2026-10-28. **Scope:** Offline Linux scientific worker research, no Lu or GitHub changes. Parent: sealed G13 cumulative archive. **NOT** a real LLM, authenticated Lu, signed publisher, or Windows isolation certification.

## Objective and outcome

Connect independent genuine scientific worker replies (EconML 0.17.0 LinearDML and causal-learn 0.1.4.8 PC skeleton) with G13's G10/G11/G12 research assurance replay in a bounded, typed request/decision/receipt envelope. Preserve explicit abstention for model intent escalation and avoid **incorrectly calibrating the real worker dataset with G9–G12 synthetic evidence that originated from a different fixture**.

### Actual experiment

The isolated Linux Python 3.13 environment from G5 (`g5env`) was reused **without redistributing libraries or binaries**. The same development-only worker path and test-double authorization/isolation flags previously used at G5 launched genuine child processes. Both scientific backends executed and produced Protobuf replies:

| Backend | Library pin | Fixture | Result | Status |
|---|---|---|---|---|
| EconML `LinearDML` | `econml==0.17.0` | 100 observations, 2 subgroups | subgroup effects `1` and `0` in this fixture | typed scientific candidate only |
| causal-learn `pc` | `causal-learn==0.1.4.8` | 250 observations, 3 variables | undirected skeleton edges `(0,1)`, `(1,2)` | typed scientific candidate only |

Each worker request and output was checked using existing `verify_mature_receipt`. G14 independently replayed G13 research assurance and bound the bridge to trace/conversation/task IDs. **The G13 synthetic source and scientific-worker observations are NOT the same dataset; its calibration cannot be transferred.** Both accepted bridge results carry `research_only=true` and all authorization, real-world causal-proof, source-authentication, and same-data calibration flags false.

The two scientific experiments were repeated twice. Their scientific result payloads, with the timing field zeroed for comparability, yielded identical SHA-256 hashes across repetitions; full response-frame hashes differ because wall time is recorded. The recorded JSON file contains the final run's raw hashes and timing-independent scientific hashes. The report auditor validates the result/report shape but does **not** independently authenticate the source of its JSON evidence.

## Scientific trust and adversarial boundary

A local attacker can construct a plausible Protobuf worker result matching expected reference values and pass the existing *structural/sanity* checker. G14's tests deliberately demonstrate this. **Neither those structure checks nor local SHA-256 receipts establish process identity, publisher attestation, OS isolation or causal identification.** The G14 policy never permits action, real-world causal claims or intervention recommendations, even for a structurally valid result. It explicitly abstains on upstream denial, evidence tampering, mismatched scope, model assertions of causal proof, and action intents.

The current G14 `WorkerAssuranceRequest` can be assembled by any test caller; no authenticated Lu host controls that assembly yet. Developer-only `host_authorized=True` and `host_isolation_attested=True` are not actual Lu security evidence. The genuine worker execution succeeds on Linux but Windows Job Objects / consent / revocation are **not tested**.

## Verification

- Focused G14: **21/21 passed**, including forged-result, replay, scope mismatch, false-authentication and evidence-auditor tests.
- Selected C14: **620 run, 37 optional skips, 583 passed**, zero failures (before the seven G14 evidence audit cases were added; audit cases passed separately). For the final C14 suite, rerun below.
- C13: **141 run, two optional skips, 139 passed**, zero failures.
- Protobuf: **48/48 schemas** compiled independently; compiler-derived descriptor bindings matched.
- G13 adversarial acceptance report: **32/32 audited and deterministically replayed**, zero authority grants.
- Genuine worker smoke: **2/2 external scientific subprocesses passed**, zero external action grants.

Run from the source checkout:

```bash
PYTHONPATH=. python -m unittest tests.test_c14_p4e_g14_bridge tests.test_c14_p4e_g14_evidence -q
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python -m unittest discover -s tests -p 'test_c14*.py' -q
PYTHONPATH=. python -m unittest discover -s tests -p 'test_c13*.py' -q
PYTHONPATH=. python -m tools.run_c14_p4e_g13_verify_report
# Requires locally pinned installed EconML + causal-learn in a separate Python 3.13 venv:
PYTHONPATH=. /path/to/venv/bin/python -m tools.run_c14_p4e_g14_real_worker_smoke
PYTHONPATH=. python -m tools.run_c14_p4e_g14_audit
```

## Next gates

1. Real LLM model caller trial using an actual locally served model, with model identity, quantization, prompt/tool-call protocol and WITH/WITHOUT comparison recorded; no GGUF or reachable model endpoint was available in this research runtime.
2. Authenticated source/signed publisher provenance and a trusted host-owned worker launch record; shape validation alone can be forged.
3. Actual Windows x86-64 sandbox/Job Object/conversation consent/permission revocation tests; developer test-double flags cannot substitute.
4. DoWhy official tagged v0.14 release provenance and exact signed dependency chain remains an independent open gate.
5. Held-out causal transportability and proof of identification remain unverified; no intervention authorization.

**No Lu repository changed; no persistent Cognitum Library upload.**
