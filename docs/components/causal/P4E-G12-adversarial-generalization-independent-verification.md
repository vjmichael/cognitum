# Cognitum C14 P4E G12 — Independent Mechanism Stress and Assurance

**Status:** Offline research reference completed. **NOT** real-world causal validation, production authorization, nor Windows containment acceptance.

## Invariants retained from G11
- G10 and G11 source files, calibration reports, and Protobuf schemas are **unmodified**. G12 pins the exact G11 gate source SHA-256; the G11 gate independently checks G10 and G9 and replays its upstream request.
- Any upstream G11 abstention remains an abstention; the G12 gate never grants external action, intervention advice, or real-world causal claim authority. G12 may report **synthetic stress-test diagnostics only**, not approve the submitted real-world domain. A source/metric mismatch rejects.
- G12's study uses a distinct data generator with different seeds and structural relationships; G9/G11 calibration thresholds are **not transported** to its scenarios.
- Data are deliberately synthetic; sufficient statistics are published, not private user records.

## G12 study design

Six **predeclared, distinct** DGPs; 80 seeds per case, 300 and 900 observations: **960 datasets** total. Outcomes and treatments are binary. The *generator* knows the counterfactual oracle, but a model or estimator observing the data cannot assume those latent facts are known.

| Scenario | Source mechanism | Oracle population ATE | What breaks |
| --- | --- | ---: | --- |
| CLEAN_INTERACTION | Observed Z affects T and Y, Z-dependent treatment effect; independent U affects Y | 0.23 | Naive adjustment omission and model interaction; stratifying on Z works under assumptions |
| HIDDEN_COMMON_CAUSE | Unobserved U drives both T and Y; Z observed but unhelpful | 0.02 | Exchangeability; adjusted effect remains biased |
| MISMEASURED_CONFOUNDER | Observed W is a 30% misclassified version of true confounder Z | 0.05 | Residual confounding after adjustment for W |
| SELECTION_COLLIDER | Inclusion depends on treatment and observed outcome | 0.15 | Conditioning on selection creates a misleading association |
| TRANSPORT_SHIFT | Z-dependent treatment effect, target P(Z=1)=0.85 vs source 0.5 | 0.39 | Calibration transport without new validation |
| NEGATIVE_CONTROL | Randomized treatment with no causal effect | 0.00 | Spurious sampling associations / false confidence |

**Estimator comparison:** unadjusted treated-minus-control risk difference and an observed-Z-stratified risk difference. G12 is not a new confidence-interval coverage experiment and does not rank mature libraries.

## Independent verification boundary

G12's `causal_g12_independent_verifier.py` intentionally does not import the G12 generator or the G9/G10/G11 calculations. It independently recomputes 960 observed 2×2×2 contingency-table risk differences, verifies sample sizes, the predeclared oracle constants, case partition, arithmetic, mean absolute error aggregation, assumption labels, and forbidden authority flags. The entire frozen report is SHA-256 pinned and the separate generator can replay all records deterministically.

**Limit:** a verified report digest and correct arithmetic do **not** prove that a synthetic generator reproduces real-world relationships. The verifier does not cryptographically authenticate third-party data; nor does it perform structural identification or external intervention verification. A malicious actor with write access to both the checker and its pinned artifact could rewrite both. Signed trusted-source attestations and Lu permissions remain outside this reference.

## Assurance policy

Every valid case abstains from causal *generalization* because it belongs to a new synthetic domain; known violations produce `ABSTAIN_ADVERSARIAL_CAUSAL_GENERALIZATION`. Even the clean cases return `ABSTAIN_NEW_UNCALIBRATED_GENERATOR`. Upstream G11 abstentions are not upgraded. Untampered records may support a plainly labeled synthetic research diagnostic, but no G12 receipt grants real-world claim, intervention recommendation, or other Lu action. Failing digest, upstream receipt, unknown case, false inference flags, or substituted metrics are rejected or explicitly unavailable.

## Security and release gates still open

- No Windows x86-64 Job Object / restricted-token or AppContainer confinement test; no verified authenticated Lu host admission.
- No independent provenance/production certification of the DoWhy main snapshot; Tigramite GPLv3 redistribution requires review.
- No LLM-with/without-Cognitum controlled quantization benchmark.
- This is **not** clinical, legal, financial, or other real-world intervention advice.
- We have not shown whether the new G12 gate improves actual LLM behavior; it supplies typed evidence and restrictions that a trusted Lu orchestrator could later consume.

## Reproducible commands (project root)

```bash
PYTHONPATH=. python tools/run_c14_p4e_g12_verify_report.py
PYTHONPATH=.:tests python -m unittest tests.test_c14_p4e_g12_adversarial -v
PYTHONPATH=.:tests python tools/run_c14_p4e_g12_smoke.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c14*.py' -q
PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c13*.py' -q
```

The G12 study generator is intentionally isolated from source archives in the parent checkpoint; the cumulative ZIP includes all scripts, Protobuf contracts, generated bindings, source and evidence.
