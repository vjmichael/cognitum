# Cognitum P19 — HDC/KAN/SSM training-artifact readiness (Linux-only)

**Date:** 2026-11-01, America/Phoenix  
**Baseline:** recovered P18 Linux source archive, unmerged research/test overlay  
**Disposition:** scoped research implementation and regression **PASS**; real HDC/KAN/SSM training acceptance **NOT COMPLETE**; production promotion **DENIED**.  
**Separation:** Cognitum research only. No Lu edits; all Windows-specific tasks remain deferred.

## Exact state of P18 components before P19

- **C08 `hdc_optional.py`**: **no learning and no training persistence**. Deterministic SHA-256-derived 256-bit BSC role/entity atoms, XOR binding, Hamming ranking against caller-supplied canonical snapshot. The source/index snapshot identifiers do not contain model weights. The result does not grant citation authority.
- **C09 `kan_optional.py` / `kan_portable.py`**: **inference from externally supplied `.npz` bytes**. `PortableKAN.save`/`load` serialize `__meta_json__` plus per-layer `grid`, `spline`, `mask`, optional `base`, `bias`. The research inference loader is pinned by SHA-256, bounded and refuses pickle. **It has no trainer or optimizer/training-history checkpoint.** P18 admits 1–2 layers, up to 8 inputs/outputs within shape and archive limits. A generic `[in,16,out]` trainer from the supplied guide cannot be sent through this C09 loader without a separately gated format/capability change.
- **SSM `ssm.py`**: fixed bounded diagonal recurrence `h[t] = a*h[t-1]+B*x[t]`, `y[t]=C*h[t]+D*x[t]`. Coefficients and initial state are supplied by each request; **no learned parameter store, state persist, or training**. `h[t]` is runtime activation/state, **not** a trained model weight. The current reference limits are 8 state/input/output dimensions and 64 time steps per call.

## P19 completed additions (research-only)

1. `cognitum/research/hdc_training_p19.py`: deterministic supervised *token-classification* HDC prototype separate from C08, with 256/1,024/2,048/4,096/8,192-bit bipolar token encodings via SHAKE256, one-pass class centroids, and bounded misclassification-only update epochs. Training rows are encoded once and reused. A checkpoint is compressed NPZ with int32 class centroids and canonical JSON metadata (`encoder`, dimensions, ordered labels, training row count, epoch config, dataset SHA). **No original training tokens or raw rows are stored**. Load requires exact external SHA pin and validates ZIP member bounds, NPY headers and shapes before allocation. It is not a trained retrieval-memory engine, LLM hidden-state encoder, or authorized runtime router.
2. `cognitum/research/kan_training_record_p19.py`: canonical, bounded JSON *receipt* paired to existing research KAN `.npz` by SHA-256. Records task, supplied data digest, hyperparameters, metrics, layer count, and explicit `optimizer_state=not_saved`, `train_resume_supported=false`, `production_approved=false`. Runs the P18 safe KAN loader for structure validation. **Does not perform training, verify self-reported metrics, certify accuracy, or authenticate the checkpoint's origin.**
3. `cognitum/specialists/ssm_artifact_p19.py`: canonical, strictly parsed JSON coefficient snapshot (`a`, `b`, `c`, `d`, dataset digest, version), SHA-256 pinned on import. No live `initial_state`, optimizer state, or training procedure; the current example is explicitly `trained=false`, `production_approved=false`. This will support a future offline SSM system-identification trainer without confusing activation memory with model parameters.

## Observed local tests

- Combined targeted P17/P18/P19 HDC/KAN/SSM research suites: **30 passed**, two expected `zipfile` duplicate-name construction warnings in tests deliberately producing bad archives. Test group includes reference HDC/SSM mathematical checks, portable KAN decoder security tests, model artifact roundtrips, forged huge NPY shape denial, duplicate member denial, checksum mutation, provenance flag tampering, malformed JSON and fixed-capacity training rejection. These are **not** the full worker or Linux cgroup tests.
- Development wheel `cognitum_core-0.1.0-py3-none-any.whl` rebuilt, entire `RECORD` verified, and installed in a separate target directory; independent HDC + SSM artifact import/roundtrip smoke passed.
- **Synthetic only:** 150 explicit-labeled training examples and 150 disjoint generated test examples sharing easy anchor tokens; all five dimensional sweeps achieved 150/150 correct, with 256-bit model smallest. This checks plumbing, NOT LLM tool-routing generalization or memory retrieval. Such high accuracy is expected on this deliberately separable fixture and cannot justify selecting D or enabling production. Training duration is a short local CPU microbenchmark, not GPU performance.
- No KAN training and no SSM training occurred during P19; only checkpoint format/readiness tests.

## Recommended next training sequence

1. **HDC router pilot:** define fixed-label ground truth for 3–8 Cognitum specialist routes with balanced real task traces; hold out families/sources/episodes to avoid leakage. Baseline with C08 deterministic routing and a no-HDC policy. Freeze LLM; cache permitted feature extraction once. Compare 1k/2k/4k/8k and one-pass vs 5/10/20 correction epochs. Report routing accuracy, calibration/abstention, latency, false tool dispatch, size and cold-start memory; no model promotion without threshold evidence.
2. **KAN numerical specialist:** select bounded numerical-function datasets (input normalization, analytic truth and derivative where applicable), train with pykan/efficient-kan/FastKAN offline as appropriate; export to existing bounded C09 NPZ and check predictions against the trainer, including out-of-domain rejection. Evaluate held-out RMSE, worst-case error, speed, monotonicity/continuity, quantization and prune behavior. Distinguish **inference-only checkpoint** from **resumable training bundle** (would additionally need optimizer state, sampler/RNG state, environment lock and raw dataset version).
3. **SSM feasibility study:** choose a real sequential target (filtering, forecasting, tool state summaries). Train constrained stable diagonal `a` and `B/C/D` by supervised gradient descent or system identification; validate stability, state chunk/resume, distribution shift and error propagation. A saved activation `h[t]` is operational state and must be stored separately from model parameters with scoped lifetime/authorization.

### Data and authority guidance

The supplied `Training HDC and KAN Components Efficiently.md` guides **offline cached-feature training**, centroid updates, KAN basis/normalization selection and measured tier promotion. Those suggestions are *training plans*, not evidence of Cognitum's present implementation. Store versioned model and training receipts in a host-controlled Cognitum artifact directory; avoid accepting arbitrary file paths through an inference request. SHA-256 pins bytes but **does not authenticate provenance**, authorize a tool, verify metric truth, or justify causal conclusions. Preserve existing sandbox, worker and Lu separation.

### Pending gates

Writable delegated cgroup-v2 live enforcement and OS-supervised recovery remain blocked/unverified. P18 intermittent all-in-one worker-suite hang remains unresolved. C14 G25N scientific interval-width gate remains a no-go. Windows/P15 remain deferred.
