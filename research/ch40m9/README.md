# CH40-M.9 — whole native-search + independent-proof pipeline

**2026-11-03 America/Phoenix (2026-11-04 UTC)** · Cognitum research only · **C14 scientific release NO_GO**.

## Question

Does M.8's safe exact-key rational-proof reuse still help after accounting for real native FLINT/MPFR branch-and-bound search and full process overhead, rather than only the proof verifier microbenchmark?

## Design

- 15 **original** CH23 frozen 127-node/64-terminal dataset traces and CH40-K acceptance pins; no synthetic substitution, rewriting, or re-signing of historical CH40-J records.
- Execute **unmodified** `CH40M7/worker_m7.py` with both native producers (FLINT 256-bit and MPFR 256-bit) on the **same original Fisher-Gram upper-bound rule**. Preserve the existing selective branch policy, widest-coordinate split, parent-cap inheritance, source pin verification, and **online independent rational verification of every child**.
- Every native worker is isolated as its own process under 1,500 MiB virtual-address-space, 20-second wall, bounded OS CPU and the experiment's *requested* 1.15-second process CPU cutoff (atomic splits can overshoot). Alternate which backend goes first across original cases.
- Use `/usr/bin/time` to measure each **complete subprocess**, not just the kernel or Python's post-import timer; capture peak RSS separately. A failure/time-limit/absent source **refuses** the experimental record.
- Independently audit the **same 30 accepted journal files** with unmodified `CH40M8/audit_m8.py` in *two separate processes*, cache disabled and enabled. Each auditor checks the original trace hash, exact parameter boxes, every child cap, inherited caps, selection, event hash chain and final frontier; it imports **neither** native producer.
- Cache key: `(original_trace_sha256, PSD_GRAM_DOMINANCE, canonical exact rational box)`. Entries are never accepted from disk or a model/producer. The verifier computes a rational reference on the first occurrence in this process. A cache hit is a reused previously proved proposition, **not** a skipped comparison.
- Verify cached and uncached independent receipts, the full proof ledger, their SHA commitments, and each journal's actual bytes all match before declaring engineering acceptance. Both audit modes are required.

## Executed full original-data results

| Measurement | Value |
|---|---:|
| Original cases | 15/15 |
| Native research worker runs | 30/30 |
| FLINT/Arb completed splits | 78 |
| MPFR completed splits | 70 |
| Native FLINT whole subprocess CPU | 28.64 s |
| Native MPFR whole subprocess CPU | 29.24 s |
| **Whole native search CPU (both arms)** | **57.88 s** |
| Online independently checked child bounds | 296/296 |
| Second, external independently checked child bounds | 296/296, both modes |
| Independent rational computations without reuse | 296 |
| Independent rational computations with exact-key reuse | 156 |
| Safe matching-box reuse hits | 140 |
| External **uncached** audit CPU | 28.72 s |
| External **cached** audit CPU | 18.06 s |
| **Whole paired-batch pipeline CPU — uncached** | **86.60 s** |
| **Whole paired-batch pipeline CPU — cached** | **75.94 s** |
| Observed paired-batch CPU reduction | **12.31%** |
| Maximum native-search worker peak RSS | 426,084 KiB |
| Maximum external auditor peak RSS | 618,524 KiB |
| Material per-case FLINT upper-frontier wins (threshold 1e-10) | 3/15 (12 ties, zero MPFR wins) |
| Frozen finite-root 0.05 certified target achieved | **0/15** |

**Interpretation:** We have measured an actual combined-search-and-audit speedup from **reusing independently proved duplicate box bounds**. The cached auditor still checks every bound. On the same 15 cases and same Gram rule FLINT produces somewhat more splits per CPU-second (78/28.64 vs 70/29.24); because the search cutoff is not precisely equal *full subprocess* CPU, this is an observed result rather than a decisive replacement criterion.

**Limits:** The observed 12.31% is a benefit for a *paired multi-journal batch*, where boxes repeat. A standalone single-backend one-shot production request cannot automatically claim this savings. The initial audit executes uncached then cached, and OS page cache warming may favor later execution; run `replicate_auditor_order.py` on the same original journals to test the reverse order. This is a single nonrandomized search trial; no statistical confidence interval, no whole-Lu-model trial, and no recovery/resume experiment yet. Test-level safety and journal atomic writes are maintained, but crash/restart correctness is a distinct gate.

The optimization does **not** replace the independently trusted rational verifier or improve the global upper-bound mathematics. Signed CH40-J historical evidence remains unchanged. **C14 scientific NO_GO** until the 0.05 finite-root condition is rigorously met and causal-identification assumptions are separately validated.

## Reproduce

Research dependencies: unmodified original frozen CH40-K trace files and pins, CH40-J rational checker, CH40-L/L2/L3 original search helpers, CH40-M.5F FLINT Gram kernel (local research path `CH40M5`), CH40-M.7 workers, CH40-M.8 independently rational auditor, native python-flint 0.9.0 and libmpfr. The original test used Linux Python 3.13.5; research-only wheel directory `CH40M3/site`; OpenBLAS/OMP threads fixed to one.

```sh
export CH40M9_WORKSPACE=/path/to/frozen/research/workspace
export PYTHONPATH="$CH40M9_WORKSPACE/CH40M3/site:$PYTHONPATH"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python research/ch40m9/run_m9.py --out /tmp/ch40m9-repro --cpu-budget 1.15 --wall-limit 20
python research/ch40m9/replicate_auditor_order.py --input /tmp/ch40m9-repro/journals --output /tmp/ch40m9-reverse
python -m unittest discover -s research/ch40m9 -p test_m9.py -v
```

**Repository scope:** Only research-specific orchestration, tests, compact mathematical results and provenance. The original ~800 MB frozen input cases, user-downloaded native packages and historical signed CH40 certificates must remain external and immutable. This is not a Lu deployment or Cognitum production enablement.

## Reverse-order audit control (completed)

Ran the *same* original 15 cases and the *same* 30 native journal files, with the independent **cached auditor first** and **uncached auditor second**. The separate auditor processes accepted the **identical rational proof ledger and journal receipt commitment** as the initial experiment. Measurements:

| Sequence | Fresh full batch CPU | Cached full batch CPU | Whole-batch CPU saving |
|---|---:|---:|---:|
| Fresh → cache | 86.60 s | 75.94 s | 12.31% |
| Cache → fresh | 85.81 s | 75.66 s | 11.83% |

Auditor-only times in the reversed order: 27.93 s fresh, 17.78 s cached. This reduces the risk of misattributing simple OS file-cache warming to exact-key proof reuse. It remains two sequential benchmark samples without a statistical uncertainty estimate. Both audit orders accept **296/296 bounds**, with **140 exact proof-reuse hits**.

## Verification gates

- **13/13 local M.9 tests pass**, including missing/duplicated frozen source refusal, modified receipt, tampered journal bytes, edited proof statement, false scientific release and missing case refusal. Tested against real two-case pilot and the real final 15-case evidence (no fabricated acceptance fixture).
- Both auditor modes exactly match every read-only journal receipt, proposition ledger, hash commitment, case/engine coverage and 296 child counts. The original frozen input SHA pins remain enforced during search and audit.
- The two-run reversed-order test also rechecked and matched the original receipt/ledger commitments.

**Next gate:** specifically measure crash/restart and trusted verifier boundary overhead, evaluate durable signed proof-key caching only if authorization/revocation/source-version invariants can be enforced, and establish replication on longer and held-out search frontiers. Production C14 remains default-off.
