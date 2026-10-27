# C08/C09 / P0 — Recovered HDC/KAN Archive and Reuse Audit

**Audit date:** 2026-10-26  
**Status:** **Archive recovered, integrity verified and unit/self-tests independently passed**; **C08/C09 P0 integration research remains open**.  
**Source:** User-owned ChatGPT Library root archives; no Zog Zoo project source or Windows user folders changed.  
**Related:** [Build order](../../build-order.md), [Lu × Cognitum host contract](../../lu-cognitum-integration.md), [component lifecycle](../../roadmap.md)

## 1. Recovered immutable source artifacts

The original files are preserved in the user's **ChatGPT Library** at:

| Library path | SHA-256 observed | Purpose |
|---|---|---|
| `/Zog_Zoo_HDC_KAN_K4_Integrated_2026-10-25.zip` | `1a054696c26e5350ae93f7150f6846bae973f6ff1aa0934fde92f264dba5a229` | Integrated experimental HDC/KAN source, tests, baselines, training/portable inference and historical reports (199 ZIP entries) |
| `/Zog_Zoo_K4_Optional_KAN_Depth_Addon_2026-10-25.zip` | `fc2809aa8bd8a681edf67c55a65d8b32ddcfca312cdc70104e27a63db8709a64` | Separate optional additional-depth overlay, default-off (6 entries) |
| `/Zog_Zoo_HDC_KAN_Closure_2026-10-25.zip` | `9aa0ac380a6ff4b020d0ca2bf4e3f663722e29b43af2ae37c249d480b9841b72` | Preserved 2026-10-25 closure report, validation logs, both above archives and `SHA256_MANIFEST.json` |

**Integrity:** Recomputed SHA-256 of both external source/overlay archives exactly matches the checksums in the closure bundle's embedded `SHA256_MANIFEST.json`. ZIP internal integrity tests returned no error; inspected member paths were relative, without parent traversal, and had no symlink entries. Source/overlay copies were extracted **only into a temporary test staging directory**; original Library assets remained unchanged.

This artifact identification is specific and independently recoverable. It is **not** permission to copy the user's entire closed research archive into another public repository or claim third-party licenses on the user's work.

## 2. New independent test run (not merely historical report)

**Procedure:**
1. Materialized three user-owned Library archives to isolated analysis storage.
2. Compared external K4/overlay hashes with the closure manifest.
3. Created a fresh temporary staging directory; extracted K4, then the optional depth overlay, after ZIP safety/integrity checks. This is the combined setup reported in the original closure.
4. Ran `python -m unittest discover -s tests -p 'test_*.py' -q`.
5. Ran `python -m zogzoo_hdc.selftest`.

**Observed results:**

| Test | Fresh outcome |
|---|---|
| Unit tests, including the KAN-depth overlay | **41 tests, all passed**; unittest elapsed **1.844 s** in this test environment |
| HDC self-test | **20/20 passed**, including BSC algebra/capacity, FHRR/HRR checks, BM25, memory, search/rescoring and fixture controls |
| OS/platform | Linux x86_64 CPU; Python in the test environment was 3.13.5 (reported by installed environment) |
| GPU/FPGA/Windows tests | **Not run** |
| Performance baseline replication | **Not run** in this fresh pass |
| End-to-end Lu + loaded-transformer improvement | **Not run**; no Cognitum↔Lu integration exists yet |

The archived closure reported these same test counts on an earlier environment. This run verifies the same observable result on current copies; no claims of statistical superiority, production readiness, or security follow from passing the tests. Do **not** overwrite the original historical measurements with these current pass reports.

## 3. Implemented source entry points (AST/source inspection)

| Capability | Recovered implementation entry points | Intended Cognitum integration role |
|---|---|---|
| Core HDC VSAs / binary, float and complex encodings | `zogzoo_hdc/models.py`: `BSC`, `MAP`, `FHRR`, `HRR`, base `Model` | Local, optional compute kernels; not trusted storage or policy |
| Associative retrieval / lexical and reranking controls | `zogzoo_hdc/memory.py`: `Bank`, `BM25Index`, `rescore` | **Derived** candidate relation/retrieval index for C08; canonical state in Lu-controlled exact store |
| Portable KAN inference | `zogzoo_kan/portable.py`: `PortableKAN` | CPU NumPy inference without requiring PyTorch for prediction |
| Trainable KAN variants | `zogzoo_kan/advanced.py`: `KANV3`, `KANLayerV3`; spline and RBF basis helpers | Optional learned numerical specialist (C09), never presumed exact arithmetic |
| HDC-derived KAN input feature building | `zogzoo_kan/hdc_numeric.py`: `NumericHDCBridge`; `k2_features.py`: `HDCFeatures` / `TrainNormalizer` | Composite research interface, requiring data provenance and fixed conversion version |
| KAN deployment helper | `zogzoo_kan/deployment.py`: `Predictor`, `save_preprocessor` | Candidate versioned model/checkpoint loader with controlled source and resource budget |
| Depth extension overlay | `zogzoo_kan/depth.py`; `tests/test_kan_depth_optin.py` | Keep **default off**; may only enable explicitly and when benchmark/compatibility requirements pass |

These classes/functions are **code entry points, not validated Cognitum service contracts**. Do not turn approximate search hits into access grants; derived HDC indexes must be invalidated or rebuilt after canonical updates, retractions and deletions.

## 4. CPU/GPU/FPGA research directions

- The currently tested code is a **CPU NumPy** implementation. That is a verified working baseline and is appropriate for initial adapter tests.
- Do not automatically inherit a historical README's “never GPU” hardware policy as a permanent Cognitum rule: the user's **current P0 design standard requires assessing CPU, GPU, FPGA and other relevant architectures** for each component. Any hardware decision must be supported by workload fit, memory/data-movement overhead, toolchain availability, portability, reliability and benchmark evidence.
- There is **no validated R9700, FPGA, ASIC or current Windows result in this fresh audit**. HDC small packed/bitwise work may benefit from CPU; large batch operations may justify GPU/FPGA research, but that is an open hypothesis. KAN portable inference may be CPU-suitable for small batches, while training/large-batch basis evaluations may warrant GPU comparisons.
- CPU-first integration **does not** imply CPU-only future development, and hardware-specific performance claims require measured real-world workloads.

## 5. Dependency-driven next steps

**C08 HDC P0 (integration):**
1. Define a bounded typed relational lookup operation against a **separate canonical store** under Lu's ownership/provenance checks.
2. Record index version and source revision; define deletion/update invalidation and fail-closed stale-index semantics.
3. Choose matched baselines: exact key lookup, SQLite FTS/BM25, graph binding, dense/binarized retrieval and the original HDC method.
4. Define the actual Lu+loaded-model questions and multi-hop/update failures to measure. Do not promote HDC based on stand-alone binary search speed alone.

**C09 KAN P0 (integration):**
1. Define a bounded numerical inference or fit operation and checkpoint format, explicitly **not** a replacement for exact calculator C05.
2. Compare KAN to simple/competent MLP/B-spline, conventional numerical interpolation/regression and solver where applicable, with held-out/OOD tasks and equalized budgets.
3. Verify checkpoint provenance, preprocessing, model size, inference precision, CPU load, and separate training-resource costs. Preserve default-off extra-depth behavior.
4. Measure Lu+actual-transformer end-task changes only after C04 native CE and C03 harness are ready.

**Security/priorities:** this source inspection and fresh test run do not grant autonomous tool access. C01/C02/C04 are prerequisites for real Lu integration. The existing research source remains archived—not deployed or added to Cognitum's default tool catalog.

## 6. Provenance and changes

- User's Library research was **read** and independently tested from copies; no original Library file changed.
- Temporary analysis copies/test directory were used. No Windows AppData directories, Lu code, GPU device or production model state were touched.
- This document records hashes, paths, source entry points and fresh independent test results so future integrators can retrieve **the actual completed work** rather than regenerate K4 from memory.
- Scientific status: *closed archived research milestone; reusable experimental code; end-to-end Cognitum/Lu integration and comparative validation outstanding*. 
