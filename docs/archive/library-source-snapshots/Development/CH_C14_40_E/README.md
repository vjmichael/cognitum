# Cognitum CH40-E — Producer-emitted MPFR proof traces

**Research-only scoped acceptance. Production/scientific status: NO_GO.**

This phase instruments a SHA-256-verified *research copy* of the CH29 original
MPFR solver to emit exact base-2 endpoint traces from the actual optimized
calculations. It does not edit the frozen CH39 archive or the accepted CH40-D
work. The independent checker reconstructs the source model, entire split
geometry, exact dyadic MPFR intervals, direct Loewner and entropy upper bounds,
Fisher positivity, coupled SPD dual tangents, and inherited parent caps using
Fraction and a separately implemented Decimal transcendental interval engine.

**Accepted scope:** 15/15 original frozen CH23 root case traces; all 127
original producer bound nodes of `one_event_n80_i00` (44 selected coupled
caps, 83 direct caps, 94 dual candidates), all 127 inherited caps, zero
unsupported displayed caps in that one full-tree case; 17 adversarial tests.
An unmodified SHA256-pinned CH29 solver produced the identical proof fields
for that 127-node case. The independent root-box gap remains unresolved.

**Not accepted:** historical Taylor/Newton actions (none accepted in this
127-node CH29 case), independent mathematical algorithm without shared
libmpdec `exp/ln` assumptions, 14 more complete 127-node producer trees,
real CH39 signer/attestor handoff, unbounded/global optimality, production
promotion, or native Windows execution of the producer instrumenter.

## Reproduce

`Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip`
should be beside these scripts, with external SHA256
`9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b`.

On Windows with Python 3.11+, **read-only evidence replay** (no MPFR DLLs):

    RUN_CH40E_WINDOWS_READONLY.cmd

It independently checks the 15 saved producer roots and full 127-node proof
trace, saving `CH40E_READONLY_RESULTS/CH40E_READONLY_AUDIT.json`.

On Linux with native MPFR/GMP and Python 3.11+ (actual producer execution):

    python prepare40e.py --archive Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip --output producer_workspace
    python run_trace40e.py --archive Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip --case one_event_n80_i00 --nodes 127 --reuse-workspace
    python verify_trace40e.py --archive Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip --trace results/one_event_n80_i00_127_original_mpfr_trace.json

`compare_baseline40e.py` compares the original uninstrumented CH29 code against
this trace-producing research copy on a locally extracted original source
layout. Saved baseline-equivalence logs are in `results/`.

Each untrusted local bound without a witness **must be refused**. No local
witness may be used to assert global optimality or CH39 signer authorization.