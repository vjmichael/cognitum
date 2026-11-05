# Cognitum CH40-D: independently checkable local mathematical witnesses

**2026-11-03. Research-only engineering milestone.**

## Executive result

CH40-D introduces four classes of **fully represented new local proof
witnesses**, all checkable by independent numerical source code against
original externally pinned CH23/CH29 finite-box data. The acceptance run
produced 60/60 independently validated local witness receipts across all 15
original datasets. The final re-audit decoded original sealed case certificates
from the SHA-256-pinned CH39 reproduction archive and recomputed every saved
bound and trace. The 36-method adversarial and positive unit suite passed.

**It does not certify archived MPFR producer float cap displays.** These
historical claims remain unauditable until the original producer emits its
full numerical witness. All 15 remain mathematically unresolved; unrestricted
global optimality and scientific production release remain **NO_GO**.

## New proof objects

| Witness class | Original cases | What the separate checker recomputes |
| --- | ---: | --- |
| Direct | 15 | Every row-wise likelihood enclosure; positive Fisher determinant and declared upper cap |
| Coupled | 15 | Pinned SPD dual, rational tangent support for every row, tangent value/slope/probability/majorant and logdet constant |
| Taylor | 15 | Objective/score at exact midpoint, full Hessian on local box, second-order remainder cap |
| Newton/Krawczyk | 15 | Exact center, preconditioner, score and box Hessian, Krawczyk enclosure, sound interior-only contraction/exclusion/refusal |

Newton classifications: **five** local contractions, **two** interior
stationary exclusions, **eight** no-gain results. These are not modifications
to the frozen original 127-node producer tree, whose Newton event count is 0.

## Independently detected numerical issue

The first CH40-D attempt used Python's default 28-digit Decimal context when
formatting some Hessian trace endpoints near magnitude 10^28. This narrowed
certain recorded intervals by an absolute amount of order 1. An independently
recomputed Hessian correctly refused several zero-event cases. The emitter was
repaired to use explicitly directed 85-digit rounding with an appropriate
relative padding. Taylor upper bounds are now computed from the *published
outward Hessian enclosures*, not hidden producer intermediates. Similarly,
the Krawczyk enclosure is derived from public score/Hessian trace intervals.
All four difficult zero-imbalanced cases then passed re-audit, and the final
15-case, 60-witness frozen-data check completed with 0 failures.

## Arithmetic trust boundary

Producer: CH40-B independently implemented Decimal interval math (85 digits).
Verifier: CH40-D exact rational algebra for direct/coupled and a **separately
written** directed Decimal derivative/Hessian engine (95 digits); no imports
of the producer's mathematical routines. Both depend on Python/libmpdec for
transcendental `exp/ln`, which is a remaining shared runtime dependency, not
an algorithmically independent transcendental library. This is not a
formally verified C or interval-arithmetic kernel.

All numerical claims are verified against an original model and box bound to
source SHA256. Malformed, missing, smaller or stale numerical intervals are
refused. The research scope is immutable and no certificate asserts an
unrestricted or finite-root global-optimality result.

## Next required acceptance

1. Adapt the **original MPFR-producing CH29/CH39 code path** to emit explicit
   equivalent witnesses for the optimized upper caps actually produced there;
   reject an archival displayed number lacking a directed trace.
2. Run the independent CH40-D verifier over those *new original-producer*
   certified traces, including Newton and Taylor when actually invoked.
3. Independently replay full node-level inheritance and global finite-root
   gap with certified local bounds; test downstream 0.05 threshold.
4. Only then integrate the signed research receipt with CH39's live separated
   Linux attestor and repeat cross-UID attacks. Keep Windows portability
   evaluation separate from independent scientific validation.

Production C14/G25 and Lu were unchanged. GitHub remains a source/evidence
repository, not the development execution host.