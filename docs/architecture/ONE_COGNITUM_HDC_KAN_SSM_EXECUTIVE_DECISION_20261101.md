# Executive architecture decision: one Cognitum distribution, all specialist families

**Decision date:** 2026-11-01  
**Status:** accepted product direction; implementation acceptance staged separately.

The Cognitum project **includes HDC (C08), KAN (C09), and SSM** as first-party components alongside mathematical, causal, symbolic, temporal, memory, formal-verification and future cognitive systems. The project shall not split into a "scientific calculator" distribution and a separate HDC/KAN/SSM distribution. There is **one Cognitum package**.

Distinct algorithmic maturity and real-world usefulness shall govern **capability selection, authorization, warnings, benchmarks and production readiness**, not exclusion from the product. Do not claim that HDC is superior to lexical/dense retrieval, that KAN universally beats MLPs, or that a reference linear SSM is a trained Mamba/S4 family model without qualifying evidence.

Engineering rules:
1. Use Cognitum's existing first-party registry, contracts, workers and provenance. Keep components individually testable but ship them together.
2. Include HDC representation/candidate retrieval, portable KAN approximate inference and SSM temporal-state processing without conflating them with exact calculators or causal certification.
3. Preserve source-revision invalidation, authenticated evidence boundaries and KAN checkpoint integrity/approval/revocation. Bundling never grants a tool permission to execute.
4. Recover previously built and benchmarked HDC/KAN code rather than gratuitously rewriting it. Develop learned SSM variants and performance improvements as **submodules of the same package**, not another installation.
5. Maintain honest benchmarks against conventional alternatives and actual transformer augmentation tasks; retain meaningful refusals, uncertainty and provenance.
6. **Cognitum stays completely independent of Lu Core** on both Windows and Linux. Any Lu-Linux branch used during development is a temporary test environment based on the latest verified stable Lu build, not Cognitum's distribution or runtime.
7. Keep GitHub as repository/documentation, not the primary development hub.

**Implementation ledger:** `cognitum/unified-hdc-kan-ssm-20261101` contains the first unified code and one-wheel packaging candidate. Its 44/44 reconstructed-component tests and 260 independent numerical checks are **not** full-repository production acceptance. The historical C08/C09 P3 safeguards are restored in that branch; full present-branch P3 retesting, Windows/Linux packaging, learned SSM and matched transformer benchmarks remain open.

This document is the user's product design decision, **not approval to promote the candidate code or change Lu**.
