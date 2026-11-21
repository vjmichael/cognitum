# COG-05-SSM-04-R5 — fixed-duration bounded-memory streaming of integrated Ito observations

**ACCEPTED exact-source native mathematical R5-R1 qualification (2026-11-21): 5/5 original GitHub Actions jobs passed; 177 tests per native target × four genuine Windows/Linux Python 3.11/3.13 environments = 708/708 passed, 0 failures/errors/skips.** The original accepted source SHA is `ea49aad581eecc346eddf7f3abcdbee5add5e444` (not the later documentation-only closeout commit). Research-only CPU linear-Gaussian mathematics. This is not full continuous-path sensing, a formal covariance enclosure, nor authorized Lu/MEL execution.

## Scientific contract

Model: `dx=A x dt+dW, dY=H x dt+dV`, with joint instantaneous process/sensor noise covariance rate `[[Q,N],[N.T,R]]` PSD and `R` strictly positive definite. Each input is a **real integrated increment** over a strictly increasing interval, or `None` for missing data. All cross-rate and correlated-integrated-increment Gaussian conditioning is delegated to the previously accepted R3/R4 primitives. Never substitute an endpoint sensor sample or a held deterministic rate.

New public interface `FixedDurationIncrementSmoother(...,lag_duration=D,noise_cross=N,initial_time=t0,max_pending_states=M)` supports:

- `push(t, deltaY)`: atomically ingest an interval ending at `t`, returning newly released state estimates. An interval ending **strictly after** state time `s+D` is excluded from that state's estimate, even if the interval spans the cutoff. If the endpoint is **exactly equal** to `s+D`, its entire integrated observation is included.
- `advance_watermark(t)`: assert no more observation increments whose endpoints are at or before event-time `t` can arrive. Release states whose duration elapsed during silence, without inferring any missing observation or Brownian path. Late/out-of-order inputs and watermark regression are refused.
- `status()`: bounded pending state/pair counts, filtered mean/root, event index, retained memory budget and scientific disclaimers.
- `initial_releases`: the initial state is immediately available for `D=0`. Otherwise pending states remain pending until a legal cutoff event/watermark.
- `fixed_duration_increment_smooth(...)`: finite batch convenience that collects released outputs, intentionally **not** bounded-output-memory; use the stateful class for bounded streaming.

Every release contains `state_time`, `observation_cutoff_time`, `conditioned_through_time`, `release_time`, original state index, QR factor, posterior mean/covariance, and explicit refusal of certification/installed execution authority. The release time can be later than the target cutoff when no event occurs exactly there; the **information cutoff never overshoots the requested duration**. This is an important difference from naïvely selecting the first *later* event for an event-count lag.

## Mathematical method and memory

- Integrate one bounded interval at a time with the accepted augmented Van Loan Gaussian cross-covariance and conditioned **adjacent state pair**. R4's rank-aware conditional backward gain and QR residual-factor recombination remain the authoritative smoother.
- Maintain only pending states and their adjacent-pair Gaussian conditionals (at most `M<=256` nodes and `M-1` pairs, with one additional transient state/pair during an atomic update). A single backward sweep releases a due prefix, rather than doing quadratic repeated smoothing for a burst.
- If `M` would be exceeded, **raise before committing any state changes**. No silent dropping, auto-flush, late conditioning, zero-imputed increments or unbounded in-memory release history.
- Individual sample gaps `dt<=16`, state/sensor dimensions `<=8`, lag duration `0..256`, finite numerical clock `<=1e8`, and bounded total accepted count `<=1,000,000`. Long overall streams (more than the R3 batch's 256 increments) are supported without retaining past history.
- A watermark is an external source/clock guarantee, not proof of an authentic signal. A later increment must end after that watermark. A silent watermark does not propagate a fictitious state to its timestamp.

## Independent mathematical qualification

The additional research tests under `research_tests/ssm04r5/test_streaming.py` use a separate ODE-integrated full joint Gaussian reference, not the implementation's Van Loan covariance, and check:
1. Multidimensional correlated noise, irregular times, missing observations, independent Schur-complement conditionals and exact cutoff handling.
2. Adversarial extremely different crossing increments cannot change already released earlier states; exact-boundary events contribute where eligible.
3. Watermark/cancellation-of-late-arrival semantics, zero-duration filtering, strictly monotone events.
4. Atomic refusal on bounded pending-window overflow and malformed integrated observations/noise.
5. A **500-event** stream with constant bounded pending memory and no in-object release accumulation.
6. A finite collector's trailing incomplete states, without a fabricated final update.
7. Twelve randomized irregular correlated-noise Gaussian reference cases.

Local development harness passed **21/21** focused tests; it used source-equivalent R3/R4 helper interfaces and is **not** a substitute for exact native qualification. The new exact Git blobs are:
- `cognitum/research/ssm_stochastic_streaming.py`: `731208b392d3a948ee7677c2e24f1117e2c8df79`
- `research_tests/ssm04r5/test_streaming.py`: `826e1a7402cf89ae5c8855cbe52fd8280617c73a`

## R5-R1 exact-source native acceptance — 2026-11-21

- **Original immutable qualifying GitHub Actions run:** [#44910714525](https://github.com/vjmichael/cognitum/actions/runs/44910714525), attempt 1, original HEAD `ea49aad581eecc346eddf7f3abcdbee5add5e444`, conclusion **SUCCESS**.
- **Five original jobs: 5/5 success.** Four native mathematical regression jobs each passed **177 tests**, covering original `ssm04`, `ssm04r1`, `ssm04r2`, `ssm04r3`, `ssm04r4`, and new `ssm04r5`; no failures, errors or skips. Native environments: Ubuntu Python 3.11, Ubuntu Python 3.13, Windows Python 3.11, Windows Python 3.13; total **708/708** passed.
- **Fifth independent GitHub CI job:** downloaded the original four native evidence artifacts and verified four exact commit identities, 10 Git blob hashes each, 177 original JUnit test case identities per environment and zero failed/errored/skipped cases. Its original JSON receipt status was `PASS_FIXED_DURATION_CORRELATED_STREAMING_AND_LEGACY_SOURCE`.
- **Separate external evidence verification (outside CI):** downloaded all five original GitHub artifact ZIPs again through the GitHub connector, compared the ZIP SHA-256 checksums to authoritative GitHub Actions artifact digests, independently checked each archive's ZIP CRC, parsed all original JUnit files, verified 177 **identical** case IDs and 21 new R5 cases in every environment, original SHA and 10 matching original Git blob IDs, and checked the original fifth-job receipt. Independent manifest: [SSM04_R5_NATIVE_ARTIFACTS.json](SSM04_R5_NATIVE_ARTIFACTS.json).
- **No genuine source failures, no repairs.** Previous accepted R3/R4 source/test Git blobs and the two new R5 Git blobs are intact. Exact qualifying source remains the original `ea49aad581eecc346eddf7f3abcdbee5add5e444`; no new R5 mathematical implementation/test revisions were needed.
- **One-time trigger retirement:** the branch-scoped automatic `push` trigger in `.github/workflows/ssm04r5-native.yml` was replaced by `workflow_dispatch` only in the same **[skip ci] docs/CI-control-only** closeout commit. No second qualifying run was created, no force-push and no mainline merge. Manual dispatch for a workflow that lives only on a research branch may require default-branch registration.
- **Scientific scope limitations remain:** no certified enclosure of roundoff or covariance eigenvalues, no physically calibrated or authenticated external sensor path, no durable checkpoint format and no installed protected MEL execution authorization.

**R5-R1 closeout status: ACCEPTED for exact-source native mathematical qualification only.**

**Remaining beyond R5:** physical sensor source custody; durable checkpoint recovery/serialization of streaming state; installed protected MEL admission and authorization; independent high-condition-number and roundoff stress; nonlinear/filter mismatch and true continuous-path sensing.
