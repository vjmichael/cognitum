# Decision: one Cognitum distribution includes HDC, KAN, and SSM

**Date:** November 1, 2026  
**Decision owner:** project owner, explicit executive decision  
**Scope:** Cognitum, all supported operating systems. **No Lu code or Lu integration.**  
**Implementation status:** single-wheel **integration candidate** on `cognitum/unified-hdc-kan-ssm-20261101`; not a claim of a fully certified production release.

## Executive decision — no two packages

Cognitum is a **heterogeneous cognitive augmentation system**, not merely a scientific calculator. HDC, KAN, SSM, exact mathematics, causal reasoning, memory, formal checks and other specialists belong in the same first-party Cognitum distribution. There will be **no separate Cognitum-brain package** versus a calculator-only package. Scientific criticism and benchmark shortfalls affect *routing, assurance, maturity and performance claims*, not whether a component is part of Cognitum.

Only one Python distribution is defined: `cognitum-core`. HDC/KAN/SSM kernel sources are shipped under `cognitum`. NumPy, Protobuf and cryptography are normal required dependencies in this integration candidate. Historical extra names `research-hdc-kan` and `research-hdc-kan-verified` remain inert compatibility aliases **to the same distribution**, not second package variants.

## Capabilities and honesty

| Component | Shipped capability | Important limitation |
| --- | --- | --- |
| **C08 HDC** | SHA-256-based binary-spatter role/entity binding and bounded candidate ranking; restored P3 epoch-aware derived-index invalidation and durable source revision controls | Candidate similarity is **not** canonical-memory access, a citation, retrieval superiority, or authorization |
| **C09 KAN** | Recovered K4 portable NumPy checkpoint inference; restored P3 signed metadata approval and durable signer revocation sources | Only approximate, bounded CPU inference; no trained checkpoint supplied, no domain-independent MLP advantage, no calibrated uncertainty |
| **SSM** | New bounded CPU *diagonal linear* discrete-time sequence recurrence with explicit state input/output, stable diagonal transitions and chunkable streaming | Not Mamba/S4, not learned parameter estimation, not full arbitrary SSM, not causal/physical certification |

The standalone `cognitum.temporal_filter` classical Kalman reference is distinct and **must not be relabeled as a trained SSM**. A trained selective/structured state-space backend is future work within this same package, not another distribution.

## One native Cognitum specialist surface

- `cognitum.plugins.specialists.Specialists` supplies a `Manifest` with `specialist.hdc`, `specialist.kan` and `specialist.ssm`; it uses the existing Cognitum `Registry`, `Runtime`, `Request`, `HostContext` and disposable-worker contracts. No new plugin framework.
- HDC and KAN inputs maintain the existing bounded canonical Protobuf contracts; the adapter carries byte frames as canonical base64. HDC returns **candidates only**; KAN returns **approximate** predictions. SSM accepts bounded strict JSON containing exactly `parameters`, `inputs`, `initial_state` and returns explicit state/outputs without persistence.
- The manifest track is `research`, not an authoritative inference engine. **Bundled != auto-enabled, visible to model != authorized, executed != scientifically certified.** The current native runtime still requires explicit research admission. `python -m cognitum specialists` reports installed operations; `--enable-specialists` enables them only for that research CLI process.
- KAN inference requires **`COGNITUM_TRUSTED_KAN_SHA256` set by the trusted host** to the exact checkpoint digest; a request cannot approve its own checkpoint. This environment-based gate is an initial standalone host configuration, **not** a substitute for P3 trusted-signer and durable permission integration.
- The P3 source files are recovered *unchanged* from `research/c08-c09-durable-revisions-p3-2026-10-30`: `hdc_index_lifecycle.py`, `kan_approval.py`, `durable_integrity.py`, generated `kan_approval_pb2.py` and `test_research_durable.py`. Restoring source preserves work but does not imply its complete present-branch integration and platform tests have passed.
- Existing C14 G25 estimator production algorithms, Cognitum research guard, and Lu were not altered by this integration.

## Acceptance evidence and scope

**Local reconstructed-component tests:** original C08/C09 P1 baseline **15/15**; unified runtime/SSM/security tests **29/29**; combined **44/44**. Exact current Cognitum `contracts.py`, `runtime.py`, `registry.py`, `policy.py`, `worker.py` and `tracing.py` have known matching Git blob identities with the reconstructed reference. Full current mainline suite was **not** run in this isolated build workspace.

**Independent numerical diagnostics:** fixed-seed 160 diagonal SSM sequences versus matrix-based NumPy recurrence (max abs difference 2.78e-16), 50 original HDC role/entity candidate checks, 50 KAN portable RBF predictions versus an independently computed Gaussian sum (max abs difference 2.19e-7; float32 method). The KAN diagnostic tolerance was corrected from 2e-7 to 1e-6 after one float32 roundoff deviation; this was a diagnostic adjustment **not preregistered holdout tuning**.

**Packaging check:** `python -m pip wheel . --no-build-isolation --no-deps` produced one `cognitum-core` wheel from a reconstructed component-only source; a clean target-prefix install imported HDC/KAN/SSM and listed all three operations. **That preview wheel is not a complete current Cognitum repository build and must not replace a full installation.** The canonical repo branch now carries the equivalent packaging and implementation changes to build one full wheel once the entire branch is checked out.

## Required next gates before production promotion

1. Reconcile this branch with the latest complete Cognitum source, execute the **full** existing test matrix, and build/install the complete Cognitum wheel on Linux and Windows (not only component preview).
2. Revalidate restored P3 source and signer-key revocation/invalidation against the current repository, not solely its original October 30 branch.
3. Attach HDC to canonical scoped memory only through authenticated authority and invalidation; independently benchmark against exact lookup, FTS/BM25, graphs and dense/binarized retrieval. Candidate IDs cannot be emitted as verified citations.
4. Benchmark KAN against matched MLP/SwiGLU and conventional numerical alternatives on unseen data, with checkpoint provenance, device-resource limits and out-of-domain refusal. Document hardware claims separately.
5. Implement and evaluate trained SSM/Mamba-family, selective/long-context alternatives, streaming, state reset and numerical stability; compare against a classical state-space baseline and transformer models under matched budgets.
6. Design capability routing that selects only empirically helpful specialists, records provenance, exposes limitations and honors cost, privacy and user requests; remain first-party **inside Cognitum**.
7. Document package size, operating-system install experience, dependency compatibility and rollback; maintain no coupling with Lu Core.

## Design constraints

- **One Cognitum package**, independent scientific subsystems, one shared first-party registry.
- Specialists may coexist without competing for memory or implying each is better than baselines.
- No automatically trusted external checkpoint, arbitrary code, path or OS permission from user/model output.
- No DLC dependency, socket dependency, second Lu application, merged Lu Core or Cognitum-to-Lu integration.
- Research provenance is kept, with no false claims of learned SSM or mathematical/causal certification from HDC/KAN.
- GitHub is the repository/version ledger. Local execution and scientific acceptance are separate.

**Result:** HDC/KAN/SSM are restored as bundled first-party Cognitum source in a single distribution candidate; final cross-platform full-repository acceptance and advanced learned SSM maturity remain open.
