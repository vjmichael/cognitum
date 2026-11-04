# C14 causal-specialist integration closeout (component, not Lu release)

**Decision date:** 2026-11-03. **Development:** C14 component code freeze after P1/P2 adapter acceptance; **not** model-enabled, not an approved Lu extension, and not production security certified. **Lu efficacy acceptance:** deferred until the pre-Lu-2.0 integration campaign. **CH40 global 0.05 proof gap:** intentionally shelved; no further research-only work.

## What is implemented

A bounded, canonical domain-specific Protobuf interface `cognitum.causal.v1` with five named operations, which use **maintained scientific engines**, not custom optimization:

| Operation | Maintained backend | Output | Current test evidence |
|---|---|---|---|
| `ate_statsmodels` | statsmodels OLS, HC3 | conditional-assumption-dependent linear ATE with HC3 CI | **Actual installed library executed** |
| `ate_dowhy` | DoWhy DAG identification, backdoor linear regression | DAG-identified backdoor ATE with library CI | Adapter mock + API review; actual library **not installed/tested** |
| `conditional_effect_econml` | EconML LinearDML | effect at explicit modifier profile with library interval | Adapter mock + API review; actual library **not installed/tested** |
| `discover_pc` | causal-learn PC | oriented/undirected graph edges, no effect | Adapter mock + API review; actual library **not installed/tested** |
| `discover_pcmci` | Tigramite PCMCI / ParCorr | lagged associations and FDR p-values, no effect | Adapter mock + API review; library **not installed/tested**, GPL host-policy gate default **OFF** |

**Do not label mocks as native engine tests.** Cross-platform wheel/ABI, full DoWhy/EconML/causal-learn/Tigramite execution, and final license distribution approval are not claimed.

## Input, assumption and uncertainty contract

- Bounded 512 KiB canonical Protobuf input, 2–12 unique safe column identifiers, 40–2,048 fully finite complete-case rows, strictly typed fixed scientific operation IDs, fixed named backend methods. No dynamic `eval`, user-authored code, arbitrary graph parser input, shell, file or network access.
- Binary `{0,1}` treatment; minimum observed treatment/control counts; sample-size and rank/conditioning checks. **This only detects crude observed overlap, not conditional positivity.** Invalid settings fail explicitly.
- Causal estimation requires user-declared **consistency, no interference, conditional exchangeability and positivity**. These are *declared*, not machine-proven. DoWhy additionally needs a bounded explicit **acyclic DAG**; its identified adjustment set must agree with the caller's. Discovery requires explicitly declared Markov, faithfulness, sufficient observability, and IID/stationarity conditions appropriate to the selected algorithm.
- All treatment-effect operations require a **finite interval that actually contains the finite estimate** and an explicit confidence level and interval method. Absence, nonfinite endpoints, incompatible shapes or other invalid library outputs produce sanitized `error` and **no effect**. The statistical coverage of intervals is not independently calibrated by these smoke tests.
- PC and PCMCI output **graph/discovery statements, not treatment effects or confidence intervals**. PCMCI emits p-values marked as FDR-adjusted link statistics, not effect sizes. Unknown edge directions remain uncertain.
- Every successful response marks underlying assumptions and causal identification as **unverified**. No `global_optimum`, `certified_causal_truth`, or CH40 research numerical guarantee is advertised.
- Missing dependencies respond `unavailable` without silent fallback; policy-gated Tigramite responds `license_review_required`; unexpected backend exceptions do not leak private data; there is never a success-with-zero fallback. Numeric libraries execute in-process, so caller **must** enforce separate process CPU/memory/wall-time controls before production execution.

## Installation and testing

Minimal core remains dependency-free; Protobuf and scientific engines are optional extras, not auto-enabled:

```bash
python -m pip install -e '.[causal-stats]'
python -m unittest discover -s tests -p 'test_c14_closeout.py' -v
```

Separate optional extras `causal-dowhy`, `causal-econml`, `causal-discovery`, `causal-timeseries-gpl` are for individual hosts to evaluate. The GPL backend requires **trusted host** `enable_gpl_tigramite=True` after license review; the request wire cannot enable it. The core does **not** import any optional causal engine at module import time.

Actual run example (inside a separately authorized, isolated host process):

```python
from cognitum.proto import causal_pb2
from cognitum.causal_specialists import run_causal_wire
req = causal_pb2.CausalRequest(schema_version=1, operation='ate_statsmodels',
                              columns=['T','Y','W'], alpha=0.05,
                              treatment='T', outcome='Y', adjustment=['W'],
                              declared_assumptions=['consistency','no_interference',
                                                    'conditional_exchangeability','positivity'])
# append >=50 COMPLETE numeric rows with both T=0 and T=1, then:
reply = causal_pb2.CausalReply.FromString(run_causal_wire(req.SerializeToString(deterministic=True)))
# Check reply.status == 'completed', reply.has_effect, reply.has_interval, limitations.
```

## Closeout vs release gates

- **Complete now:** production-target source adapters, fixed Protobuf schema, input/assumption/uncertainty/error tests, real statsmodels numerical verification, stable CI entry.
- **Open deployment blocker:** actual numerical integration tests of four optional packages on Windows/Linux with pinned distributions; Tigramite GPL distribution review; OS resource/worker admission via C02; pre-Lu-2.0 C03/C04 model-in-the-loop efficacy study. **Do not declare these passed or silently enable C14.**
- **No further C14-only CH40 research:** no 0.05 proof-gap work, no M.12 bespoke security kernel, and no additional numerical algorithm invention. General OS containment and key custody belong in C02. All existing CH40 evidence is immutable and can be consulted if future product needs justify it.

## API anchors

DoWhy's `identify_effect`/`estimate_effect`, EconML's `LinearDML` and `effect_interval`, causal-learn's `pc`, Tigramite `PCMCI.run_pcmci`, and statsmodels HC3 robust covariances were checked against official library documentation. Availability of Python packages and their licenses must be validated by downstream packaging. Tigramite is GPLv3-or-later; it must not be silently added to the application's standard dependency set.
