# CH40-M — established solver migration and cross-component library-first audit

**Status:** scoped and ready for implementation. **Not a claim of benchmark success.** C14 scientific release remains NO_GO.

## C14 integration experiment

Separate three layers:
1. **Causal identification and estimators:** existing DoWhy/Tigramite/causal-learn/EconML/statsmodels/R baselines where applicable. No numerical optimizer can repair confounding or unidentified effects.
2. **Numerical candidate/feasible incumbents:** SciPy/Ipopt (plus established Firth/brglm2/logistf baselines).
3. **Rigorous arithmetic and global bounds:** FLINT Arb or MPFI for outward enclosures and determinants; IBEX for interval contractors/global branch-and-bound where it can represent the exact objective; SCIP as strong optimizer comparator, not automatic interval proof.

### Fixed 15-dataset benchmark

- Preserve original CH23/CH40-J dataset SHA-256 and run/case mapping; do not replace with synthetic data.
- Evaluate the exact same Firth-like objective, penalty, data transforms, parameter boxes, precision and stopping criteria. Validate definitions on small exact cases before interpreting performance.
- Record separately feasible point objective lower bounds, proven region upper bounds, finite-root residual gaps, verified leaf coverage, undefined/singular Fisher information, timeout and refusal.
- Compare legacy CH40-L.2/.3/.4 evidence with library-generated candidates, but do not add overlapping gains or compare unlike node budgets.
- Use matched CPU core/time/memory budgets in addition to identical work counts; measure cold/warm worker startup and Windows/Linux packaging.
- Use two independent arithmetic implementations when possible. Document shared algorithm assumptions and all unsupported API cases.
- Declare victory only with an equal-or-stronger independently checked bound, correctness and stability, plus a material throughput/maintenance/deployment benefit.
- Never substitute a solver's success status for a proof; 0.05 target remains an explicit certified global finite-root gate.

### First practical implementation sequence

1. Inspect actual local shared libraries, headers, Python wheels and licensing; pin versions and sha256.
2. Build a thin feature-flagged FLINT/Arb verified-evaluation adapter; compare interval likelihood and Fisher logdet bounds on frozen cases against CH40 verifier.
3. Build an IBEX interval contractor/B&B prototype on the same parameter boxes, or record why modeling the Firth objective is not feasible.
4. Benchmark SciPy/Ipopt initial incumbents and SCIP global-search baseline without conflating approximate and rigorous results.
5. Produce 15-case side-by-side datasets, independent checks, CPU/memory telemetry, and explicit go/no-go per backend.

### Cross-component sweep

Priority 1 (math duplication): C05, C10, C11, C13, C14.  
Priority 2 (existing domain toolchains): C15, C16, C06, C08, C09, C17, C19.  
Priority 3 (contracts/unique policy and host integration): C01–C04, C07, C12, C18.

For each component write: current custom code; best standard candidate; adapter needed; held-out tasks; licensing and target OS; independent oracle; benchmark; decision keep/replace/compose/retire. Do not claim integration before source, tests and CI verify it.

### Promotion limits

CH40-M is initially **research-only**, no Lu host modification and no production enablement. Original CH40-J signed chain and scientific NO_GO status are unchanged. A dependency version or certification category change requires requalification.
