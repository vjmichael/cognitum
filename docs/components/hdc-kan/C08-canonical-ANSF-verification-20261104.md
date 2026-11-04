# C08 — canonical ANSF candidate verification (2026-11-04)

## Implemented P2 reference boundary

The existing C08 BSC/HDC adapter computes *candidate identifiers* only. It is
not a fact store, a source of truth, or a tool permission system. The new
`cognitum/research/hdc_canonical.py` independent verifier:

- Requires an explicitly pinned host-provided snapshot identifier and revision.
- Decodes both request and candidate response with strict deterministic
  Protobuf parsing and rejects unknown or duplicate wire fields.
- Recomputes the HDC ranking and Hamming distances instead of trusting an
  arbitrary worker/model response.
- Resolves the latest canonical revision for each source before applying
  scope, tombstone, and relation matching.
- Rejects a prior source if its current revision was deleted, reassigned to
  another scope, or changed relation.
- Emits only **exact-matching authorized** source IDs, canonical revisions,
  and opaque host citation handles; no candidate is a citation by itself.
- Keeps false/approximate HDC matches out of the verified result.

## Lu ownership

Lu Rust ANSF/SQLite FTS5 is the canonical owner. PR #21 in Lu introduces a
host-authorized FTS5 read bridge for existing ANSF message revision chains.
The bridge is not yet a typed relation extraction API. Until a host-approved,
version-pinned and access-scoped `CanonicalRelation` snapshot provider is
available, this C08 implementation is an isolated reference component.

Cognitum must not parse arbitrary model text into "trusted relations", mint
permissions, create a second persistent canonical SQLite database, or
return HDC scores as if they established that a relation is factually true.

## Release gates still open

1. Verify the dedicated Windows/Linux Python 3.11/3.13 acceptance matrix,
   including existing C08/C09 regression compatibility.
2. Implement an actual Lu Rust authenticated canonical relation snapshot
   provider binding workspace/session access checks and current ANSF revisions
   to the C08 typed protocol, with crash/restart and stale snapshot negatives.
3. Initial synthetic 32-record BSC/canonical verification latency and false-positive/recall accounting is added in `tools/run_c08_candidate_benchmark.py`; still run full baselines against host FTS5/BM25 and exact relation lookup
   with held-out data, false positives, latency/memory and model task outcomes.
4. Verify through Lu's native model tool registry only after C02 policy
   authorization, host trust receipts and C06/C07 evidence semantics are
   accepted.

**Status: C08 candidate verification implemented; host integration and
production gates remain open.**


## Baseline-first decision (new)

HDC remains **disabled by default** and has no privileged/authoritative
path. `cognitum.research.hdc_admission` is an inert policy helper that
requires all of the following before an experimental HDC candidate route
can be selected: user opt-in; an independent Lu host approval; at least
30 benchmark trials with a host-authenticated source; zero verified false
positives; recall at least as high as conventional exact retrieval; and
at least 1.25x measured median query speedup. If any criterion fails,
use **exact matching or ANSF's existing SQLite FTS5**. This is deliberately
conservative, not a claim that HDC is superior.

`tools/run_c08_conventional_baselines.py` compares exact canonical lookup,
SQLite FTS5 and native BSC + strict canonical recheck over the same 32-record
synthetic relation snapshot and 60 deterministic query trials. It reports
query latency and recall separately, plus FTS5 build cost. Results are
preliminary: they do not represent full Lu tool dispatch, long-memory,
domain evaluation, energy consumption, hardware SIMD/GPU or user tasks.

The C08 BSC implementation currently uses Python arbitrary-length integer
XOR and `bit_count()`, *not* any claimed specialized GPU kernel. No
performance-advantage or specialized-hardware assertion is accepted without
matched native CPU and hardware benchmarks. If conventional methods
outperform it, retaining C08 as an experimental optional library is valid;
there is no requirement to promote it into Lu core.


## Scope correction: HDC is a family of research methods

C08's current code implements a **small Binary Spatter Codes (BSC) subset**:
256-bit SHA-256-derived role/entity binding with XOR and Hamming distance,
plus strict host canonical candidate revalidation. It is **not a complete
HDC/VSA implementation**, not an optimized portable SIMD/kernel library,
and not a definitive test of HDC as a computing paradigm.

The field also includes representations such as Holographic Reduced
Representations (HRR), Multiply-Add-Permute (MAP), sparse binary distributed
representations, tensor product representations, and other variants. Techniques
we have **not** implemented or benchmarked comprehensively include:

- Bundling/superposition with capacity and interference controls;
- Position or order encoding with permutation, sequence and n-gram binding;
- Associative cleanup memories, iterative unbinding and noise robustness;
- Online/one-shot class prototypes and incremental learning;
- Sparse/dense and binary/bipolar/real-valued hypervectors with dimension
  sweeps and realistic memory/accuracy trade-offs;
- Structured relational composition, multi-hop queries and compositional
  generalization;
- Practical portable vectorization (SIMD/POPCNT) and edge inference on
  real microcontrollers, plus optional FPGA/ASIC/in-memory accelerators.

**Two application tracks must be kept separate.**

1. **Edge / low-power research:** test classification, streaming sensors,
   incremental local learning and noise robustness against optimized tiny
   conventional baselines on the same constrained processor. Measure
   measured joules/inference or energy proxy, latency, RAM, flash, accuracy
   and reliability. Energy advantages cannot be inferred from XOR alone.
2. **Lu / high-end augmentation research:** exact and FTS5 remain default
   canonical retrieval. HDC remains an optional experiment with measured
   application-specific advantage and must never own canonical ANSF memory.

**Interpretation rule:** Failure of the present tiny BSC adapter to beat
exact or FTS5 search says only that this implementation and test workload
did not justify deployment; it does *not* falsify HDC's hardware/algorithm
research potential. Do not make a general HDC performance claim from this
prototype.

Research context:
- Kleyko et al., *A Survey on Hyperdimensional Computing aka Vector
  Symbolic Architectures*, ACM Computing Surveys, Part I (2022), Part II
  (2023): https://d3ccyth396mz21.cloudfront.net/publications/a-survey-on-hyperdimensional-computing-aka-vector-symbolic-architectures-part-i-models-and-data-transformations
- *Hyperdimensional computing hardware: progress, trends and prospects*
  (2025): https://service.jices.cn/EN/10.20193/j.ices2097-4191.2025.0047
- *Optimized Hyperdimensional Edge AI Evaluation for Efficiency and
  Reliability under Real Radiation* (2026):
  https://doi.org/10.1145/3773032

Future techniques belong behind explicit independent gates; the existence
of a research technique alone is not evidence of production readiness.
