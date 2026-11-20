# COG-05A — Scientific assurance and reproducibility index

**Status: consolidation accepted (documentation plus locally executed offline evidence auditor).** Computational reference remains the immutable, successfully tested [`826e4b9459e4b70413ef8f0813a4c41c2b609fae`](https://github.com/vjmichael/cognitum/commit/826e4b9459e4b70413ef8f0813a4c41c2b609fae), tree `0dbbeb3d5de4e65d3a7dea489e87fc7d8b56f4b8`. Its [native regression](https://github.com/vjmichael/cognitum/actions/runs/44683244710) and [integration](https://github.com/vjmichael/cognitum/actions/runs/44683244685) are 4/4 and 8/8. The prior ledger-only closeout differs from that source solely in `docs/MASTER_TASK_LEDGER.md`; no numerical kernel was modified for COG-05A.

## Research map

This is an entry point to the 21 COG-04 research stages and MEL CPU qualification, not an assertion that every K1–K60 group is complete. Earlier reports deliberately preserve local-candidate language; the relevant historical successful exact-head runs in [source_index.json](source_index.json) and the [master ledger](../../MASTER_TASK_LEDGER.md) supersede historical pending status, not the limitations. For A–N the historical native gates are recorded; the present audit does not rerun A–N or verify their historical ZIP bytes.

| Stage | Research capability | Assurance type |
|---|---|---|
| [COG-04A](../cog04a/REPORT.md) | Trainable basis foundation | Bounded learned/reference tests |
| [COG-04B](../cog04b/REPORT.md) | Certified polynomial checkpoint | Represented-function algebra/certificates and scoped numerical tests |
| [COG-04C](../cog04c/REPORT.md) | Verified graph and polynomial exchange | Represented-function algebra/certificates and scoped numerical tests |
| [COG-04D](../cog04d/REPORT.md) | Adaptive refinement/pruning | Represented-function algebra/certificates and scoped numerical tests |
| [COG-04E](../cog04e/REPORT.md) | Scalar functional arithmetic | Represented-function algebra/certificates and scoped numerical tests |
| [COG-04F](../cog04f/REPORT.md) | Sparse multivariate symbolic operators | Represented-function algebra/certificates and scoped numerical tests |
| [COG-04G](../cog04g/REPORT.md) | Cartesian fields and operators | Represented-function algebra/certificates and scoped numerical tests |
| [COG-04H](../cog04h/REPORT.md) | Polynomial differential equations | Represented-function algebra/certificates and scoped numerical tests |
| [COG-04I](../cog04i/REPORT.md) | Adaptive differential-equation learning | Learned field approximation and scoped certificates |
| [COG-04J](../cog04j/REPORT.md) | Multidimensional elliptic learning | Learned field approximation and scoped certificates |
| [COG-04K](../cog04k/REPORT.md) | Transient tensor learning | Learned field approximation and scoped certificates |
| [COG-04L](../cog04l/REPORT.md) | 2+1D space-time learning | Learned field approximation and scoped certificates |
| [COG-04M](../cog04m/REPORT.md) | Typed tensor interchange | Typed replay and actual reference workers |
| [COG-04N](../cog04n/REPORT.md) | Scoped tensor worker cooperation | Typed replay and actual reference workers |
| [COG-04O](../cog04o/REPORT.md) | Exact cross-grid L2/H1 metrics | Exact represented metrics |
| [COG-04P](../cog04p/REPORT.md) | Finite represented weak forms and Ritz spectra | Exact forms; approximate finite spectrum |
| [COG-04Q](../cog04q/REPORT.md) | Adaptive Dirichlet continuum approximation | Exact forms; independent numerical continuum convergence |
| [COG-04R](../cog04r/REPORT.md) | Affine Sturm–Liouville and D/N/Robin | Exact forms; independent numerical continuum convergence |
| [COG-04S](../cog04s/REPORT.md) | Separable rectangular 2D/3D spectra | Exact forms; independent numerical continuum convergence |
| [COG-04T](../cog04t/REPORT.md) | Coupled constant-coefficient complex adjoint modes | Exact forms; independent numerical continuum convergence |
| [COG-04U](../cog04u/REPORT.md) | Rigorous scalar continuum bounds and exact assembly optimization | Theorem-backed scalar enclosures; measured assembly equivalence |

### Claim classes and boundaries

1. Exact rational identities refer to the represented polynomial or spline functions, integration, matrix entries, replay or algebraic witnesses. They do not establish an unknown function, physical system or arbitrary PDE solution.
2. Learned KAN stages fit parameters and test finite, bounded fixtures, including learned scientific fields. Q–U employ shared spline mathematics and deterministic Galerkin/Ritz or rational comparisons, **not a trained neural network performing eigensolution**. Conventional SciPy/NumPy numerical solvers and independently constructed references are explicit dependencies. No claim of novel neural spectral algorithms.
3. Numerical eigenvalues and eigenfunctions have residual, orthogonality, convergence and independent reference checks. These are floating numerical results, not rigorous enclosures. S is separable rectangular/box, T is constant coefficient two-component Dirichlet with isolated modes, not arbitrary nonseparable operators or defective spectra.
4. U's [proof contract](../cog04u/REPORT.md) uses conforming min-max, rational inertia, piecewise constant comparison and a Poincare interpolation bound. The proof is conditional on the stated scalar self-adjoint affine coefficient class; exact interval arithmetic and witnessed matrices are distinct from independently numerical ODE shooting. The analytical pi bracket is not the approximation error. General nonnormal/coupled bounds remain open. The audit below checks retained endpoint arithmetic and provenance, not a formal proof assistant certification or new full theorem replay.

## Reproduce or inspect

- Use the complete source SHA, not current branch HEAD, and review the corresponding workflow at `.github/workflows/python-tests.yml`. The historical per-stage source SHA and run are in [source_index.json](source_index.json); Git blob pins index selected research modules, tests, reports and harnesses. They are Git object IDs, not SHA-256 content hashes. The full Git tree is authoritative.
- Existing workflow declares Python 3.11/3.13 on hosted Windows/Linux and optional extras. It resolves version ranges, not a fully frozen per-run environment. Archived MEL base receipts capture NumPy/Protobuf/Python versions and platform; complete transitive dependency wheel hashes, compiler/BLAS build/CPU metadata and physical-machine energy records are not available uniformly. Existing [scientific wheelhouse](../../integration/scientific-wheelhouse/) is an earlier separate qualification, not automatically the exact final run lock. For future studies capture a hash-pinned complete environment, CPU topology, thread settings, BLAS vendor/build, OS image and clock/measurement method.
- For an offline **evidence audit**, download the original ZIP payloads from the [native run](https://github.com/vjmichael/cognitum/actions/runs/44683244710), named `github-actions-artifact-<id>.zip`, into one folder. Preserve unchanged ZIP bytes; repacking changes the digest. [archives.tsv](archives.tsv) has 44 exact archive IDs and published SHA-256 digests, covering MEL-07A/R1/R2/R3 and O–U on all four native cells. GitHub artifacts expire; save a copy before expiry. Do not claim current availability merely because a digest is retained.
- From the repository root, run `python tools/cog05a/verify_evidence.py --manifest docs/research/cog05a/archives.tsv --archives <archive-folder> --out <new-audit.json>`. Standard library only; read-only ZIP processing, no extraction, network, model, worker or eigensolver. Verifies complete target grid, source/status, archive SHA/CRC, internal file inventory/hashes, JUnit totals, predecessor links, cross-target exact matrices and R/U identity, certificate endpoint and error arithmetic, matched timing arithmetic and MEL observed arms. A mutated manifest digest was locally rejected. No claim of semantic Protobuf replay or new mathematical solver execution.
- For **new native execution**, follow the dependency order in the immutable workflow, including MEL-07A/R1/R2/R3 then O through U with each predecessor receipt. Use the workflow-declared dependencies and BLAS single-thread settings. Reproduced numerical eigenvalues and timed costs are subject to documented tolerances and platform variation; exact matrix bytes are the stronger equivalence gate. A new environment's result is not identical historical evidence. No additional CI batch was needed to check the saved evidence.

## Newly executed COG-05A evidence audit

All 44 archives passed: 3,524 internal file hashes, 32 same-source prerequisite links, 380 O–U test executions (no failures/errors/skips), 388 exact matrix file occurrences (97 distinct stage/path identities), 288 rational interval/error identities and 144 matched assembly samples. The auditor independently recalculates benchmark ratios and checks exact matrix equality on the retained outputs, not a fresh candidate kernel execution. Historical failures and repairs remain in the ledger. The 44-archive audit includes the MEL R1/R2/R3 raw records; base MEL has one qualification JSON per target and no internal hash manifest.

### Benchmarks and what can be inferred

| Native target | U median CPU assembly speed ratio | U original peak MiB | U optimized peak MiB | MEL R3 median wall ratio, serial/adaptive |
|---|---:|---:|---:|---:|
| Linux Python 3.11 | 6.527 | 100.61–100.74 | 100.61–100.74 | 2.893 |
| Linux Python 3.13 | 6.146 | 94.09–94.34 | 94.09–94.34 | 2.911 |
| Windows Python 3.11 | 6.636 | 47.59–47.72 | 47.57–47.91 | 2.959 |
| Windows Python 3.13 | 6.100 | 51.41–51.68 | 51.25–51.50 | 3.084 |

U: 24 paired case/target ratios, six cases per target, median of three CPU samples per route per case (four nested meshes per sample); aggregate median 6.2694x, min 5.2x, max 7.0x. Equivalent 84.05% reduction computed as 1-1/median ratio. Exact matrices match both original and optimized routes and R archive in this same-head run. Assembly alone; excludes eigensolve, certificate generation, oracle and imports. No end-to-end speedup or significant peak-memory reduction established. Linux lifetime peak RSS and Windows lifetime peak working set are different metrics; do not infer OS causality from hosted runs. Separate runtime baseline vs peak; peak change is not allocation accounting.

MEL R3 final same-head requalification: 20 workload/target comparisons; 72 adaptive, 108 constrained, 196 serial worker calls; identical observed result sequences, median elapsed serial/adaptive 2.935x (range 1.393–3.756x). This is from U's final run, not a replacement for the earlier [R3 experiment](../mel/MEL07A_R3.md) at its historical exact source. Do not combine the assembly-only and worker-dispatch speedups as if independent factors. Linux sampled child counters are lower bounds; Windows worker telemetry has its own scope. Review [baseline](../mel/MEL07A_CPU.md), [R1](../mel/MEL07A_R1.md), [R2](../mel/MEL07A_R2_CLOSEOUT.md).

### Mathematical enclosure width versus error

| Case | Maximum final rigorous interval width | Maximum certified absolute error of numerical approximation |
|---|---:|---:|
| DD | 2.35515e-22 | 1.43754e-4 |
| NN | 1.04673e-22 | 4.66815e-6 |
| DN | 1.63552e-22 | 3.04605e-5 |
| RR | 0.008982693 | 0.008982423 |
| Variable DD | 1.423575831 | 1.423575599 |
| Variable NR | 0.802367827 | 0.802367567 |

Maximum over three low modes and four targets, last mesh. A rigorous but wide interval may be much less informative than a numerical convergence estimate. Do not substitute empirical accuracy for a mathematical guarantee. Neumann constant mode exact zero.

## Research extension protocol

For C++/Rust or accelerator work preserve the Python implementation as a reference. Select a single bounded kernel and freeze input/output contracts, rational serialization, limits, null/degenerate/failure cases, and proof witnesses. Use byte-identical exact results, independent mathematical replay of certificates, per-case repeated paired tests, warm/cold startup separation, time/peak/resident memory scope, fully pinned dependencies, and documented hardware/runtime; never trade exactness or execution authority for speed. Compare optimized Python and conventional competent implementations as well as original baseline: a new backend wins only if measured against the correct controls. No migration or FPGA implementation is authorized here.

## Remaining research, not release claims

- Original historical trainable K4 archive provenance and general K1–K60 coverage remain open (see [historical reconciliation](../cog04a/K1_K60_RECONCILIATION.md)). HDC/SSM research remain distinct ([HDC charter](../COG03_HDC_RESEARCH_CHARTER.md), [unified architecture](../../architecture/COGNITUM_UNIFIED_HDC_KAN_SSM_2026-11-01.md)); no fresh HDC/SSM mathematical acceptance beyond recorded MEL cases.
- General geometry, nonseparable/variable coupled operators, full degenerate eigenspaces, defective spectra and nonnormal rigorous enclosures; sharpen variable-coefficient scalar bounds.
- Environment lock/physical replication, independent theorem review, matched profiling of actual live memory, exact-native-kernel experiments and hardware validation remain open. MEL-06B-B installed Lu gate remains owner-deferred. No automatic worker/model admission or production, Lu, or accelerator promotion.

Recommended next task: COG-05B, freeze a reproducible scientific experiment/environment protocol and design a matched native exact-arithmetic kernel feasibility study; implementation only when separately selected.
