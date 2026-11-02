# CH-C14-03 — Pinned G25 source verification and local replay gate

Date: 2026-11-02. **Status: repository source integrity verified; exact local G25 test execution BLOCKED.** Linux-only research; no production C14, Lu or Windows changes.

## Source restoration status

Using the connected GitHub repository source reader, independently hashed the exact research source with a self-tested JavaScript SHA-256 implementation. Results:

| G25 research source | Actual SHA-256 | Pins |
|---|---|---|
| `baseline/g25i_core.py` | `f881ae12bdae90fa4acec0bae9046e5580f5ddad80a1794006c3da5a3f6621e4` | MATCH |
| `tools/g25_release_guard.py` | `3480952a031d17061615eaa92597e7b2f0df22495954d5656aeeb6b51322f64c` | MATCH |
| `integration/c14_research_host.py` | `74a717da88139c1a894e7d754a1dc702f5e328337ee2109017313c6a3aa2681c` | MATCH |
| `integration/g25_cancellable_supervisor.py` | `1fad033b4871be412463be7b0236d98805bf003b65a5f4a5c21060812368eeb6` | MATCH earlier published supervisor digest; not an internal pinned dependency |

Hashes refer to `research/c14_g25_nonprod/` in branch `cognitum/component-hardening-c14-review-20261102`. The first three match the frozen supervisor whitelist.

**Blocking environment:** the locally mounted P17/P18 checkout does not contain `research/c14_g25_nonprod/`; GitHub DNS/network cannot be reached from the local container. The connector returned text but did not mount the original files. Do not reconstruct approximations, waive SHA pins, or claim these exact modules executed.

## Fresh verified tests

- Existing P17/P18 causal bootstrap/variance tests: **16/16 PASS**, using the correct local source root in PYTHONPATH. **Not G25.**
- New G25 replay-driver integrity tests: **4/4 PASS**, covering missing-source fail closed, altered-source fail closed, explicit source pin whitelist and status reporting. **Not G25 scientific/host tests.**
- Pinned G25 guard/host/supervisor cancellation/receipt/numerical tests: **BLOCKED**, not performed locally.

## Source-level audit of requested cases (not execution)

- **Cancellation**: supervisor uses a separate POSIX process session for each research worker and kills/reaps process group on cancellation or timeout; late results withheld.
- **Unsupported assumptions**: guard expects explicit Gamma and written justification; absent evidence returns a non-certifying refusal.
- **Missing data**: missing observed arms and <25 observed counts are refused; host rejects malformed binary observation forms.
- **Numerical failures**: host returns `internal_failure` with null result on unexpected exceptions; supervisor rejects malformed worker receipts.
- **Provenance**: supervisor enforces exact source SHA before admission; receipt hashes validate consistency, not authenticity.
- **Open risk**: child `communicate()` reads stdout without a resource cap until after return; recorded bounded-output engineering gap, distinct from the post hoc 65,536-byte validation limit.

## Reproduction artifact and continuation

A local self-testing `retest_pinned_g25.py` replay package exists as `Cognitum_CH_C14_03_Pinned_G25_Replay_Driver_2026-11-02.zip`. For a local network-accessible Cognitum checkout run:

```bash
python retest_pinned_g25.py --source /path/to/cognitum --output ./replay_results --run-e2e
```

It fails closed if pins mismatch and runs the original guard, host, supervisor, batch tests plus 4 independent black-box supervisor parts when exact source is present. The archive is a handoff runner, **not a G25 passing receipt**. The source snapshot from GitHub should be downloaded or made accessible in the local container, then exact suites rerun.

## Release decision

**NO-GO unchanged.** Previous G25N failed 12/12 scientific precision cells; no production promotion, independent statistical review, full LR inversion or hidden-confounder solution. Do not mislabel these 20 local ancillary tests as a G25 full retest.
