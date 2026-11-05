# CH40-E — Original MPFR producer proof-carrying bounds

**Date:** November 3, 2026. **Research disposition:** Scoped Linux acceptance;
scientific release **NO_GO**.

## Why this gate matters

CH40-C established that historic `upper_bound_ceil_display` binary64 numbers
could not establish their own soundness. CH40-D independently certified newly
computed local Decimal witnesses, not the historical MPFR producer's actual
optimized bounds. CH40-E emits proof trace data **at the historical original
CH29 producer arithmetic operations**. The trusted original ZIP and CH29
source/dependency SHA256 are checked before instrumenting a *copy*.

## Math and verification

The source-instrumenter observes the CH26 direct objective, CH27 coupled dual,
and CH29 branch-and-bound code paths, without changing decisions. MPFR numbers
are exported in exact base-2 significand+exponent representation (never a
binary64 display). Each trace includes the original model/box/node identity,
all dual candidates, exact p0 tangent choices, row p/weight/loglikelihood and
supporting-line interval endpoints, SPD Q, F/U matrix intervals and Fisher
determinant lower/upper enclosures, original global loglikelihood tangents,
selected local upper cap, and inherited parent cap.

A separate checker imports none of the historical MPFR/optimizer modules.
It uses exact rational arithmetic for all algebra and a separately implemented
95-digit directed Decimal interval engine (with explicit outward widening)
for exp/log. It independently establishes positivity via a nonzero Fisher
minor and Cauchy-Binet; verifies original row-wise loglikelihood envelopes;
recomputes direct Loewner determinant and dual logdet tangent inequalities;
and checks the selected local upper against every emitted original operation.
The complete proof tree is rebuilt from rational midpoints, with verified
parent domain inclusion before cap inheritance. The independently evaluated
incumbent gives a feasible lower bound; no 0.05 finite-root gap was proved.

The Decimal transcendental engine itself is not formally proved: libmpdec
correct-rounding and directed widening are explicit assumptions, distinct
from CH29 MPFR. This is algorithmically independent source replay rather
than a machine-checked theorem in a proof assistant.

## Measured acceptance

- **15/15 original frozen CH23 cases:** complete original producer root upper
  cap independently audited, with original source/data hash pinned.
- **Original `one_event_n80_i00` full 127-node run:** all **127/127 selected
  optimized MPFR caps** certified (44 coupled, 83 direct); **94** dual
  candidate calculations independently checked; **127** inherited ancestor
  caps and source-domain splits verified.
- **Unmodified producer comparison:** original uninstrumented CH29 proof fields
  match instrumented CH29 proof fields exactly for all 127 nodes (measured
  runtimes excluded from equality).
- **17/17 adversarial/positive tests:** forged dual index, p0, interval value,
  Fisher weight/determinant, kappa, source pin, Newton insertion, display
  cap and claimed scientific promotion all rejected.
- **Scientific result:** finite-root 0.05 gap **not established**; unrestricted
  global-optimality certification remains **NO_GO**. No original Newton
  contraction/exclusion occurred in these accepted producer traces.

## Security and scope

Raw mathematical research traces are unsigned. They inherit their origin from
SHA256-pinned original inputs, a reviewed observer patch manifest, explicit
source equivalence, and independent replay; they are **not accepted CH39
five-account signed receipts**. CH39 integration is separate. Original
CH23–CH39 evidence, production C14/G25, and Lu were not modified. The
previous user's Windows 113/113 mathematical replay is not CH40-E acceptance.

## Next gate

1. Repeat the full original 127-node producer instrumentation and independent
   certification for the other 14 frozen datasets, especially all three
   zero-event ambiguous datasets.
2. If producing Taylor/Newton actions in later phases, emit and independently
   verify their actual rounding operands and proof conclusions, instead of
   synthesizing nonexistent CH29 historical Newton events.
3. Integrate only fully scoped independent mathematical receipts into CH39's
   live separated-account challenge/signature path, retaining fail-closed
   refusal and `NO_GO` scientific semantics.