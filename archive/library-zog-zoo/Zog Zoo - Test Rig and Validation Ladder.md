# Zog Zoo — Test Rig and Validation Ladder

| Field | Value |
|---|---|
| **Document Version** | 0.1 — Initial |
| **Status** | Planning / Pre-Execution |
| **Author** | Michael |
| **Date** | 2026-07-31 |
| **Companion docs** | `Zog Zo DHRA Design Doc.pdf`, `Zog Zoo Data Extraction Guide.md` |
| **Classification** | Internal research plan (living document) |

---

## 0. Purpose

This document defines **how we prove, in the cheapest possible order, that the three research components — HDC, KAN, and Capsules — work**, and *only then* scale the (commodity) transformer backbone up to production size.

The core principle:

> **The transformer backbone + SSM is the *known* part. HDC, KAN, and Capsules are the *unknown* part. We minimize compute on the known and concentrate it on the unknown.**

**Guiding boundary (do not lose this):**
A small test rig answers *"do the components work and integrate?"* It is **necessary but not sufficient** for *"does the 4B product perform?"* Component viability (Tier A/B) **earns the right** to build the product (2B → 4B); it does **not replace** it.

---

## 1. The Validation Ladder (at a glance)

| Stage | Name | Backbone | What it proves | Gate (go / no-go) | Effort (laptop-GPU scale) |
|---|---|---|---|---|---|
| **0** | Calibration | none | Baselines + thresholds set | harness runs end-to-end | hours |
| **1** | **Tier A — Component isolation** | none / trivial | each of HDC, KAN, Caps works in principle | each component passes its micro-benchmarks (or is dropped/redesigned) | minutes–days |
| **2** | **Tier B — Integration** | ~0.5B | passing components work *together* on simple reasoning | integrated system beats backbone-only baseline on target tasks | days–2 weeks |
| **3** | **Backbone scale-up → 2B** | 2B | capability holds at 2B; efficiency target met | product gates (capability + efficiency) | days–weeks |
| **4** | **Production → 4B** | 4B | full product capability + efficiency | final product gates | weeks |

**Two kinds of gates (keep them separate):**
- **Research gates (Stages 1–2):** "Do the research components work and integrate?" → go/no-go *per component*.
- **Product gates (Stages 3–4):** "Does the product meet capability + efficiency targets?" → go/no-go *on the whole*.

**Iteration policy:** The ladder is gated and *iterative*, not strictly one-way. A Stage-2 failure routes **back** to Stage 1 to fix the offending component — not forward.

---

## 2. Stage 0 — Calibration (prerequisite)

- **Set up:** GPU (16–32GB), PyTorch, a small eval harness, synthetic-data generators.
- **Record backbone-only baselines:** pick a ~0.5B off-the-shelf transformer and measure its *unmodified* scores on the Stage-2 reasoning tasks. These become the "backbone-only" reference for Tier B.
- **Finalize thresholds:** run each Stage-1 micro-benchmark at a few settings and lock in concrete pass numbers (the values in §3 are *starting targets*).
- **Deliverable:** `calibration/` with baseline numbers + a filled-in threshold table.
- **Gate:** harness runs end-to-end; baselines recorded.

---

## 3. Stage 1 — Tier A: Component isolation (no backbone)

Each component is tested on **synthetic / targeted inputs, in isolation**. A failure here points at the *component*, not the integration. Thresholds below are **starting targets — calibrate in Stage 0**.

### 3.1 HDC (cheapest — near-instant vector math)

| # | Test | Method (brief) | Pass (starting target) | Proves |
|---|---|---|---|---|
| **H1** | Associative recall | store N key→value hypervectors; query clean + noisy key | recall ≥ 90% @ N=10k, noise=20% | core store/retrieve |
| **H2** | Binding invertibility | bind A⊗B; unbind A; measure B recovery | recovery ≥ 0.9 similarity | compose-then-decompose algebra |
| **H3** | Interference ceiling | recall accuracy vs. bank fill | *characterize* the curve; know your N limit | where HDC breaks |

> **Verdict (2026-10-20, D=10k):** H1 **PASS** (NN 1.000 @ N=10k, α=0.2) · H2 **PASS** (best-per-regime: xor 1.000, conv 1.000) · H3 **CHARACTERIZED** (CAM knee N≈200–500; conv breaks below N=100; NN floor ≥ N=20k) → **HDC: GO** (with the wiring constraints below)
>
> **Findings (2026-10-20):**
> - **NN nearest-key index is the workhorse:** acc 1.000, cos ≈0.97, margin ≥0.93 at fills up to N/D = 2.0, even with 20% query noise.
> - **CAM (superposition) capacity ≈ N ≲ D/18:** XOR knee N≈200–500 @ D=10k; CONV breaks below N=100 (heavy-tailed deconvolution interference). CAM cosine-to-target decays ~1/√N.
> - **H2 regime map:** XOR clean for sign operands (clean or noisy unbind ≥0.97), weak on superposed A (0.71). CONV clean on clean + superposed A (linearity, ≥0.9999), weak on noisy unbind (0.77 mean, min 0.17).
> - **Tier-B wiring consequence:** large banks → NN side-channel; small banks (N ≲ D/18) → XOR CAM; CONV only for composing superposed operands.
> - **Metric caveat:** CAM raw `top1_sim` is the max of N random projections (grows ~√(2 ln N)); use accuracy + true cosine as the signal metrics.
>
> **New status (2026-10-24):** Authoritative test protocol = `Zog_Zoo_HDC_Strengths_Test_Matrix_v0.2.md` (C1–C7). Phase B1 (BEIR) = exploratory only. Next: Stage 0 (manifest) → Stage 1 (smoke) → Stage 2 (C1 hard gate). KAN K1 FROZEN until C1–C6 complete. Key changes: 4 VSAs tested natively, D={512,1024,4096,10000}, Torchhd cross-validation, per-architecture noise models, new C4/C5/C6 categories, matched-memory baselines, ≥5 seeds pilot / ≥10 confirmatory, pre-registered thresholds.

### 3.2 KAN

| # | Test | Method (brief) | Pass (starting target) | Proves |
|---|---|---|---|---|
| **K1** | Function approximation | learn a known f (poly / sine / piecewise); error vs. same-size MLP | error ≤ MLP | earns its place over an MLP |
| **K2** | Interpretability | extract learned edge functions; human "readable?" rating | humans judge KAN clearly more interpretable | the *actual* claim (not just accuracy) |
| **K3** | Auditable sub-computation | small arithmetic / logic task | correct **and** human-readable trace | auditable reasoning |

> **Verdict (fill after run):** K1 ___ · K2 ___ · K3 ___ → **KAN: GO / NO-GO / REDESIGN**

### 3.3 Capsules (riskiest — test the *specific* claims)

| # | Test | Method (brief) | Pass (starting target) | Proves |
|---|---|---|---|---|
| **C1** | Equivariance / invariance | same meaning, different surface form; output consistency vs. a plain-layer baseline | more consistent than baseline | core capsule property |
| **C2** | Incoherence detection | coherent vs. deliberately-incoherent inputs; AUC of the agreement/routing signal | AUC > chance **and** > a confidence baseline | the "hallucination-detector" claim (most at risk) |
| **C3** | Part-whole recovery | synthetic structured input; hierarchy recovered | recovered above threshold | structural representation |

> **Verdict (fill after run):** C1 ___ · C2 ___ · C3 ___ → **Caps: GO / NO-GO / REDESIGN**

**Stage-1 gate:** a component proceeds to Tier B **only** if its 3 tests pass (or are consciously accepted with a noted limitation). Any **NO-GO** is dropped or redesigned *before* integration.

---

## 4. Stage 2 — Tier B: Integration (~0.5B backbone)

- **Backbone:** ~0.5B off-the-shelf transformer (a real, trusted commodity) — *or* a 0.1–0.3B from-scratch backbone if design ownership is wanted.
- **Wire in** the **GO** components (per §3):
  - **HDC** as an external-memory side-channel (bind a query → decode associations back into the stream).
  - **KAN** as sub-function head(s) on the numeric/logic task.
  - **Caps** as a verification head (reads candidate output → coherence/confidence signal).
- **The simple reasoning task(s):** 2–3 tasks, each exercising one component *and* requiring them jointly. *(Define concretely in Stage 0 — e.g., a multi-step "retrieve → compute → check" task that needs HDC recall + KAN compute + Caps verification.)*
- **Measure vs. the backbone-only baseline** (from Stage 0): does adding the components **improve** the target metrics (recall / accuracy / auditability / coherence) **without** regressing general quality?
- **Deliverable:** `integration/` with the wired model + a results table (baseline vs. hybrid) per task.
- **Gate:** hybrid beats backbone-only on the target metrics within tolerance **and** doesn't regress general quality beyond tolerance → **Tier B: FEASIBLE / NOT FEASIBLE.**
- **NOT FEASIBLE →** route back to Stage 1 (fix/redesign the offending component) or re-scope the task.

---

## 5. Stage 3 — Backbone scale-up to 2B (product gate)

- Replace the 0.5B backbone with a **2B** backbone (same architecture, same GO components).
- **Product gates (capability + efficiency):**
  - **Capability:** target-task suite ≥ agreed bar (within X% of the 4B reference, or an agreed absolute target).
  - **Efficiency:** inference footprint (GB, watts, tokens/sec) within the consumer budget.
- **Deliverable:** `backbone-2b/` with a capability + efficiency report.
- **Gate:** 2B meets capability + efficiency → proceed; else diagnose (backbone too small? component wiring? data?) and iterate.

---

## 6. Stage 4 — Production 4B (final product gate)

- Scale the backbone to **4B** (re-verify the current 4B-class leaders before committing — the landscape moves fast).
- **Final gates:** full capability suite + efficiency + hallucination-rate (Caps) + auditability (KAN) + long-context (SSM) **all** within targets.
- **Deliverable:** the production model + a full validation report.
- **Gate:** all final targets met → **RELEASE / iterate.**

---

## 7. The necessary-but-not-sufficient boundary (repeated for emphasis)

- **Tier A/B (tiny)** ⇒ *component viability* — go/no-go on the **research**.
- **2B/4B** ⇒ *product capability* — go/no-go on the **product**.
- Passing the tiny rig **earns the right** to build 4B; it does **not replace** 4B.

---

## 8. Dependencies

- **Hardware:** 1 consumer GPU (16–32GB); Tier-A HDC runs near-instantly on CPU.
- **Data:** synthetic generators for §3. **No frontier-LLM API is required for Tier A** — keep it cheap and offline. Teacher-LLM distillation data is a *later* optimization, not a Stage-1 prerequisite.
- **Tooling:** PyTorch; a small eval harness; an HDC library or a ~100-line reference implementation.
- **Time (laptop-GPU scale):** Tier A = days · Tier B = days–2 weeks · 2B/4B = weeks each.

---

## 9. Iteration and failure routing

- **Component fails Tier A** → drop or redesign that component; do **not** proceed with it.
- **Integration fails Tier B** → identify which component regressed; route **back** to Tier A for that component.
- **Scale-up regresses (2B/4B)** → check backbone size vs. component wiring vs. data; iterate.
- **Every gate decision is logged in §10.**

---

## 10. Status and decision log (living)

| Stage | Status | Date | Decision | Notes |
|---|---|---|---|---|
| 0 — Calibration | not started | | | |
| 1 — Tier A (HDC) | complete — H1–H3 run | 2026-10-20 | GO (wiring constraints per §3.1 findings) | results: `Zog Zoo Dev/results_hdc_tierA.json` — **now exploratory only** |
| 1 — Tier A (HDC) | BEIR retrieval (Phase B1) | 2026-10-24 | DONE (exploratory track) | rows: `Zog Zoo Dev/results/rows_run.jsonl` |
| 1 — Tier A (HDC) | **NEW: Strengths Test Matrix v0.2 (C1–C7)** | 2026-10-24 | **NEXT: Stage 0 (manifest) → Stage 1 (smoke) → Stage 2 (C1 gate)** | protocol: `Zog_Zoo_HDC_Strengths_Test_Matrix_v0.2.md` |
| 1 — Tier A (KAN) | not started — **FROZEN** | 2026-10-21 | on hold until HDC review closes (both external reviewers + user) | unfreeze per Progress Report §13.4 |
| 1 — Tier A (Caps) | not started | | | |
| 2 — Tier B integration | not started | | | |
| 3 — Backbone 2B | not started | | | |
| 4 — Production 4B | not started | | | |

---

## 11. Open questions

- Exact Stage-2 reasoning tasks (define in Stage 0).
- ~~HDC hypervector dimension (start at 10k? test 5k / 10k / 20k in H3).~~ → **answered 2026-10-20 (H3 D-probe):** at N=10k, D ∈ {5k, 10k, 20k} all fail CAM while the NN index passes all three → keep **D=10k** for the NN side-channel; CAM is small-bank only (N ≲ D/18).
- Capsule variant to test (dynamic routing by agreement vs. a lighter equivariant head).
- KAN grid size / depth for the sub-function heads.
- Which 0.5B base model to use for Tier B (re-verify current leaders).

---

## 12. Next action

1. **Stage 0:** build the eval harness + synthetic generators, record backbone-only baselines, finalize thresholds. *(Still open — the HDC Tier-A tests ran standalone in `Zog Zoo Dev/`.)*
2. ~~**Stage 1, starting with HDC (H1–H3)**~~ — **done 2026-10-20: HDC GO** (now under review closure — Progress Report §12–§13).
3. **Now (2026-10-21): close the HDC review** — Phase B single pass (**pending user GO**, Progress Report §13.2) → Phase C record + verdict re-scope (§13.3, includes reconstructing `h2_original_lastrow_wins.py`).
4. **Then: Stage 1 — KAN (K1–K3)** (then Caps C1–C3) — **FROZEN until the user confirms HDC closure** (Progress Report §13.4).