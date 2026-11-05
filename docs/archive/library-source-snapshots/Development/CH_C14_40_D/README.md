# Cognitum CH40-D — local mathematical proof witnesses

This package adds independently checkable **new** direct, coupled-tangent,
Taylor and Krawczyk proof witnesses for the original 15 frozen CH23 cases.
**Research-only; NO_GO for global optimality or certified historical MPFR
producer float bounds.**

Use `RUN_CH40D_WINDOWS.cmd` on Windows (Python 3.11+). It regenerates 60 proof
objects and performs an independent second audit of every result.
No native MPFR is needed. The separate CH40-D mathematical verifier never
imports CH40-B's Decimal interval implementation.

**Output:** `CH40D_RESULTS/CH40D_FINAL_ACCEPTANCE.json`. The 15 individual
`case.json` reports include full published enclosures and source/witness hashes.

**Source:** sealed CH39 full archive SHA-256
`9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b`.

**Accepted development run:** 15/15 cases, 60/60 local witnesses, 36/36
adversarial and positive tests. Newton local: 5 contractions, 2 stationary
exclusions, 8 no-gain. Historical displayed cap certification: 0; no
live five-account attestation or global finite-root optimum.

See `PROTOCOL_CH40D.md` and `Engineering_Report_CH_C14_40_D.md` for the exact
scope and remaining certification steps.