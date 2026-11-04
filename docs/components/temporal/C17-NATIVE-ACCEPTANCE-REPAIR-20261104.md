# C17 native temporal acceptance repair — 2026-11-04

PR #73 historical head `5cfb299d15d3e3313d7296b4ffc3cce71f089684`
passed the real C17 native matrix on Windows Python 3.11 and 3.13, but
failed Linux Python 3.11/3.13 with three assertions:

1. Forecast input validation: The existing filter permits
   `forecast_time_ms == last_sample.time_ms` (zero-horizon forecast),
   a valid immediate state estimate. Test incorrectly expected rejection
   at exactly 39000 ms for a series ending at 39000 ms. Replaced with
   38999 ms and corrected over-horizon case relative to the last sample.
2. HMM mode-change alerts: The HMM reports the maximum-posterior state,
   but requires its *new* mode posterior to exceed the caller's
   `alert_probability` before emitting an alert. State switching and
   high-confidence alerting are distinct. Historical tests assumed the
   default .65 confidence threshold must always be crossed.
3. Typed HMM wire test made the same ungrounded alert assumption.
   Both change-alert cases now explicitly use .5 (a switch to the
   maximum-probability state among two states necessarily meets .5),
   preserving production's default .65 threshold and its caution.

The fixed tests do **not** change HMM numerical inference, temporal
input semantics, or wire authorization boundaries. They tighten the
tests' distinction between a state estimate and confidence-qualified
notification.

Shared full regression at the old head passed Linux and failed Windows
in separate Linux-only host-recovery tests, not C17 numerical tests.

New-head **Windows/Linux Python 3.11/3.13 acceptance is still required**
before merge/closure; no unverified pass is claimed.
