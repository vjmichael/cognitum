# Cognitum CH40-F — full original MPFR producer bound certification

This research-only milestone verifies each original CH23 frozen case's historical CH29 MPFR-produced finite-root branch-and-bound cap. Each of the 15 *full 127-node trees* must have an unmodified producer equivalence run plus an independently executed Fraction/Decimal proof checker. The previously accepted CH40-E case is carried forward only after its saved audit and equivalence are revalidated.

**No scientific global-optimality or production release is granted.** The 0.05 finite-root gap remains unproved in the accepted historical data; unrestricted global optimality is not tested. Original Taylor/Newton rule events are not accepted by the historical certificates. The receipt guard is a research-only interface prototype and is not installed into CH39's five-UID service or production code.

## Windows read-only audit

Extract the complete reproduction ZIP to a short path, then run `RUN_CH40F_WINDOWS_READONLY.cmd`. The command recalculates the original selected 127-node direct, coupled, and inherited bounds with an independent Fraction/Decimal verifier for all 15 cases; it does not need MPFR DLLs or the `cryptography` package. `--quick` independently replays just `one_event_n80_i00`. A 15-case run can be computationally expensive; the tool writes a progress JSON after each case. Windows verification has not yet been executed unless separate Windows evidence is supplied.

## Scientific/trust boundary

- Actual CH29 MPFR producer trace comes from an ephemeral research copy instrumented by CH40-E, with all original source and model hashes pinned to the CH39 sealed archive.
- Independent checker does not import the original MPFR solver modules. It re-evaluates exact MPFR dyads, outward interval operations, direct Loewner/Fisher certificates, coupled tangent candidates, exact partition geometry and inherited parent caps.
- Independent checker uses `libmpdec` for decimal exp/log, so a fully independent transcendental mathematics implementation remains a research concern.
- CH39 original frozen checkpoint acceptance is unchanged. `research_receipt40f.py` checks strict challenge, source, mathematical cap and original CH39 case pins; the checker owns no signing key. Its SO_PEERCRED caller must supply an actual OS-verified checker UID in the future live service.
- No private signing keys, untrusted scientific promotion, or production API changes are introduced.
