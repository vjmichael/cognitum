# C14 P1 — Discrete Structural Causal Models, interventions and counterfactuals

**Checkpoint: 2026-10-27. This is a tested, bounded mathematical reference, not a causal effect estimator from raw observational datasets, not a causal discovery engine and not a Lu-installed production capability.**

## Technology assessment — mature standards first

- **DoWhy / PyWhy:** model → identify estimand → estimate effect → refute/robustness. Backdoor, frontdoor, instrumental-variable, and ID methods belong in mature C14's identification suite; their correctness assumptions must remain visible. https://www.pywhy.org/dowhy/v0.12/user_guide/causal_tasks/estimating_causal_effects/effect_estimation_with_estimators.html
- **EconML:** heterogeneous treatment-effect estimators; useful for CATE/DML/causal forests only after a valid causal identification argument, not an alternative to identification. https://www.pywhy.org/EconML/
- **causal-learn:** PC, FCI, GES and other structure discovery (candidate graphs are **not** automatically causal ground truth). https://causal-learn.readthedocs.io/en/latest/
- **Graph library in this checkpoint:** real NetworkX 3.6.1 for ancestral/moral-graph adjustment criteria and a separate `nx.is_d_separator` verifier; no DoWhy, EconML, or causal-learn runtime installed or tested in this checkpoint.
- **Research watchlist (not implemented):** *Causal Identification from Counterfactual Data: Completeness and Bounding Results*, ICML 2026 https://proceedings.mlr.press/v306/raghavan26a.html ; *DeCaFlow*, NeurIPS 2025 https://proceedings.nips.cc/paper_files/paper/2025/hash/c78f639424b8d89ceb4f2efbb4dfe4f4-Abstract-Conference.html ; work on counterfactual identifiability and unstructured-data causal measurement. These are research candidates, **not an established advantage over classical causal identification**.

## Implemented C14 P1 functions

1. Typed `cognitum.causal.v1` Protobuf `StructuralCausalModel` has finite endogenous/exogenous states, exact parts-per-million exogenous masses, arbitrary acyclic grounded structural-function tables, source-assumption *label* (not a host-authenticated proof), an optional shared latent parent for genuine hidden confounding, deterministic variable order, and fixed parameter budgets.
2. **OBSERVATIONAL_QUERY:** exact `P(Y | factual evidence)` from the *assumed* SCM. Observational conditioning does not modify the model.
3. **INTERVENTIONAL_QUERY:** exact `P(Y | do(X=x))` by overriding the structural equation of `X` while leaving the exogenous distribution intact. This is **not** the same quantity as `P(Y|X=x)`.
4. **COUNTERFACTUAL_QUERY:** exact `P(Y_do | factual evidence)` using abduction–action–prediction, *conditioning the original exogenous assignment* on factual observations, then reusing **the same** assignment under `do`. Also returns the factual/counterfactual target joint distribution; counterfactual conditioning is never silently mixed with post-intervention evidence.
5. **BACKDOOR_CHECK:** tests the sufficient backdoor criterion for a user-specified observed adjustment set `Z`: non-descendant of treatment in the original DAG; d-separates treatment and outcome in the graph with outgoing treatment edges removed. The expanded graph includes **latent exogenous nodes**, which can never be selected as observed adjustment covariates. A failed test has **no positive evidence-valid receipt** and means *this adjustment set is not certified*, **not** that the effect is unidentifiable by every possible method. Passing it means graph-based identification *under assumed DAG/causal Markov assumptions*, not proof that the DAG is true and not an estimated ATE.
6. Independent exact checks: the solver evaluates mixed-radix function tables; the checker reconstructs structural assignments with a separate recursive evaluator and exact `Fraction` products. Backdoor graph criterion uses a separate NetworkX d-separation routine. Results may carry `ASSUMED_SCM_EXACT` or `BACKDOOR_GRAPH_CRITERION`, **never** `IDENTIFIED_FROM_REAL_WORLD_DATA`.
7. Metadata-only Protobuf receipt/audit records include request and result SHA-256, backend/version, reason code and elapsed time. Model source/evidence/counterfactual values are not logged in audit; a hostile received result cannot promote its own assurance label. All calls start **disabled** and require `host_authorized=True` in this Python reference. That parameter is a synthetic host-side guard, **not** authenticated Lu security.

## Mathematical and operational limits

- 1–8 exogenous and 1–12 endogenous variables, 2–6 states each; at most 4,096 joint exogenous assignments and 4,096 entries per structural table; fixed maximum frame and timeout. Exogenous roots are mutually independent **except where their shared influence is encoded as the same root**; arbitrary correlated exogenous roots require an explicit joint root with sufficient cardinality or a later richer SCM.
- Exact rational arithmetic only for the **supplied discrete model**. Structural equations, directions, exogenous probabilities, causal sufficiency and stable mechanisms are assumptions, not learnable/verified from the request. Conditioning on impossible factual evidence yields an explicit non-success status. Deadline/resource exhaustion yields `INCONCLUSIVE`, not a false causal statement.
- This is **not** adjustment-effect estimation, causal discovery, dynamic/time-series causal modeling, continuous SCMs, mediation/IV/frontdoor general identification, partial identification/bounds, causal fairness, or language-based causal claims. Those are later C14 implementations through mature libraries and optional research backends.
- No native Lu CE, Windows build, OS process sandbox, authenticated source provenance, production privilege admission, or full comparative benchmark. No action permissions follow from a causal query result.

## Functional reproduction

```bash
PYTHONPATH=.:tests python -m unittest tests.test_c14_causal -v
PYTHONPATH=.:tests python tools/run_c14_smoke.py
PYTHONPATH=.:tests python tools/verify_protobuf_schemas.py --require
```

Regression results are recorded separately under `P1-functional-test-evidence.json`. Compare outcomes only on typed and assumption-equivalent causal questions; cross-world counterfactuals are not observational treatment-effect ground truth.

## Next C14 milestones

- **P2:** DoWhy identification and effect-estimation adapter; test backdoor/frontdoor/IV/ID capability boundaries, observed support/positivity, uncertainty intervals, refutation/sensitivity; add independent simulated-ground-truth functional checks.
- **P3:** EconML CATE/homogeneous/heterogeneous treatment effects and causal-learn PC/FCI/GES with host-pinned disabled optional workers; separate discovered structure and identified effects.
- **P4:** Causal bounds, transportability, soft interventions and research backends with provenance/assumption sheets. Preserve benchmark hooks; defer full comparative campaign until the portfolio is built.
