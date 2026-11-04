# HDC / KAN / SSM breadth-first research recovery and fair evaluation
Date: 2026-11-04
Status: engineering coverage audit; **not** production implementation or benchmark superiority.

## Correction to research methodology

The project must not use a minimal reference kernel as evidence that an entire
architecture family is uncompetitive. First recover and test representative
major mechanisms **within each family**, then evaluate meaningful tasks against
credible baselines under matched data, budgets and hardware. "Everything"
means an explicitly inventoried, representative and justified coverage target,
not all published variants or unrestricted research forever.

Components remain in the **single Cognitum distribution**. Research inclusion
does not imply routing preference, production deployment, permission or
scientific superiority. Lu Rust ANSF/FTS5 owns canonical memory.

## Verified source-level inventory versus planned breadth

| Family | Existing checked-in main candidate | Already recovered elsewhere | Missing validated coverage |
| --- | --- | --- | --- |
| **C08 HDC / VSA** | Bounded 256-bit SHA-derived BSC XOR role/entity binding, Hamming candidate ranking; C08 draft PR #79 adds canonical verification | User-owned K4 archive audited in `docs/components/hdc-kan/P0-archive-reuse-audit.md`: `zogzoo_hdc/models.py` implements **BSC, MAP, FHRR, HRR**, with `memory.py` Bank/BM25/rescore. Archived test audit previously reported 41 unit and 20 selftests | Reintegrate original licensed/provenance-cleared BSC/MAP/FHRR/HRR tests and kernels; binding, bundling, permutation/order, cleanup capacity, incremental learning; multiple dimensions/noise/sequence lengths; portable SIMD and constrained hardware |
| **C09 KAN** | Pinned portable NumPy RBF/spline inference, at most 2 layers, strict shape/bounds; current main has no training service | K4 archive `zogzoo_kan/advanced.py` KANV3/KANLayerV3 and spline/RBF utilities, `hdc_numeric.py`, `k2_features.py`, deployment helper and optional depth overlay; unified branch includes approval gate | Reintegrate trainable spline/RBF and depth variants behind bounded policies; test optimization, interpretability/formula recovery and edge/OOD; compare strong MLP/SwiGLU, splines, interpolation/regression and exact solvers |
| **SSM / C17 temporal** | Current main includes temporal filter reference; no full learned Mamba/S4 family in main | `cognitum/unified-hdc-kan-ssm-20261101` has bounded `cognitum/specialists/ssm.py` diagonal linear recurrence and specialist routing; documentation reports 44 reconstructed component tests and 260 independent numerical diagnostics | Reconcile old branch and restore verified diagonal SSM; then build comparative trained diagonal/structured and selective SSM cases, state reset, streaming, chunk equivalence, long-range dependency, drift, numerical stability; compare Kalman/HMM/ARIMA, RNN/GRU/LSTM, TCN and attention/Transformer where appropriate |

**Important:** Recovered archive code is documented, *not equivalent to code
already merged into the present main branch*. No claim is made that all
families are fully implemented. The single-wheel unified branch is a candidate
and does not supersede later mainline changes without reconciliation.

## Implementation order with independently checkable gates

### B0 — code/provenance inventory and old-branch reconciliation
- Hash/version/license audit of user-owned archive and optional depth overlay.
- Read and diff `cognitum/unified-hdc-kan-ssm-20261101` against current main;
  preserve later security fixes and source/host boundaries.
- Track each algorithm as `present-main`, `recovered-branch`,
  `archive-only`, `not-implemented`, `tested`, `benchmarked`.
- Run original selftests, then native Windows/Linux Python 3.11/3.13.

### B1 — representative method suites
- HDC: BSC, MAP, HRR, FHRR with equal workloads; bind/unbind/bundle/order,
  associative cleanup, multi-hop, noisy patterns, online prototypes.
- KAN: portable RBF/spline, trainable variants, depth opt-in, checkpoint
  integrity/provenance, fit/predict and OOD behavior.
- SSM: stable diagonal recurrence, trained baselines, structured/selective
  transitions, chunk and streaming equivalence, hidden-state reset/replay.
- Keep each family bounded and non-authoritative; experimental adapters must
  use Cognitum's first-party registry and durable worker contracts.

### B2 — fair methods comparison, *before* promotion
Use predetermined seeds, datasets, train/validation/test partitions, model
size/parameter counts, precision, tuning budget, input/output boundaries,
identical requested operations and adversarial negatives.
- HDC versus exact relational graph, Lu ANSF FTS5/BM25, dense vector
  retrieval (where relevant), standard classical classifiers, k-NN and
  small MLPs on noisy/streaming data.
- KAN versus MLP/SwiGLU, B-splines/interpolation, polynomial or Gaussian
  process regression, classical solver in solved-function regimes.
- SSM versus Kalman, ARIMA/HMM, GRU/LSTM, TCN, attention and transformer.
- Report accuracy/task success, errors, calibration, OOD, concurrency,
  training and inference time **separately**, RAM, disk, reproducibility,
  wall-energy/power when measured, CPU/GPU device and vectorization.

### B3 — augmentation ablation
On the same fixed actual Lu model and prompts:
`without specialist` / `with each variant` / `with conventional baseline`.
Grade end-to-end correctness, tool selection, latency, resources, safety and
revision/tombstone handling. Never claim benefit from synthetic selftests.

### B4 — promotion decision by measured workload
A specialist may remain research-only while fully present in the one
Cognitum package. The default route remains an independently verified
conventional baseline until a variant demonstrates an advantage on a named,
reproducible task. **No universal verdict** about HDC, KAN or SSM may be
drawn from a narrow negative result.

## Required tracking outcomes
For every variant, record source provenance, status, platform test logs,
dataset split hashes, baseline identity/version, trained checkpoint digest
(where relevant), limits, benchmark statistics, hardware metadata and
whether it was actually exercised through Lu's model/tool orchestration.
Hardware acceleration, especially HDC low-power edge hardware, is a distinct
research track; desktop timing is not a valid proxy for joules/inference.


## Deferred research decision — ARM/low-power hypothesis (owner direction)

**Provisional interpretation of historical benchmarks, not a general HDC verdict:**
HDC may have its most compelling engineering niche in resource-constrained,
low-power devices, particularly ARM microcontrollers/embedded targets.
Current high-end Lu environments should keep HDC **research-only**.

**Do not declare HDC, KAN or SSM defeated:** the tested reference slices do
not cover all major published techniques or the project owner's earlier
recovered implementations. The comparative results are conditional on
implementations, task selection, hardware and optimization, not universal
architecture rankings.

**Deferred C08-EDGE gate:** when resumed, choose specific ARM processors and
microcontroller memory/power budgets; port representative BSC/MAP/HRR/FHRR
and incremental classifiers to equivalent optimized native kernels; compare
against optimized classical tinyML/classifiers and direct exact lookup under
identical streaming/noise workloads; report measured energy per sample,
RAM/flash, quality, cold start and update cost. Do not claim that a desktop
Python XOR benchmark measures edge energy.

**Current priority:** preserve this research direction; continue recovering
and testing the existing component work instead of diverting the entire
Cognitum development program into ARM hardware engineering.
