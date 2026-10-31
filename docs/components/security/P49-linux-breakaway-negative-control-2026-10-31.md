# Cognitum P49 — Linux process-group escape negative control

**Date:** 2026-10-31  
**Scope:** Cognitum-only local reference test; GitHub is a repository and documentary ledger, not a development hub. No Lu modifications.

## Motivation

P48's five process-lifecycle reference probes include a positive group-cancellation case for a fixed cooperative worker. That observation must never be generalized to hostile descendants. A subprocess can start a new POSIX session (`setsid`) and thereby leave the supervisor's process group. A group-targeted SIGKILL then does not necessarily reach it.

P49 adds an intentionally adversarial **negative control** to demonstrate that limitation, alongside a matched ordinary-child control. It is not a general worker-launch interface and does not add JSON repair. Cognitum's strict P47 evidence checks remain independent and unmodified.

## Implementation

- `cognitum/lifecycle_escape_negative.py` runs a fixed unprivileged Linux Python supervisor and child; both are disposable. Requires Linux `/proc`, `prctl(PR_SET_CHILD_SUBREAPER)`, `pidfd_open`, and `pidfd_send_signal`.
- Child reports readiness **without escaping**. The observer first obtains a Linux `pidfd` identifying the actual process, then explicitly releases the child from a barrier to call `setsid` (negative control) or stay in the process group (ordinary control). That avoids an early escape before the observer can reliably terminate it.
- After group SIGKILL, the negative control observes the breakaway child remaining alive. The positive control observes the ordinary child exiting. Both are explicitly reaped; the negative-control child is killed by its stable pidfd, rather than a bare PID, before the function returns.
- The generated local diagnostic records a demonstrated process-group containment gap, **not** a successful production worker security gate. This new receipt is *not* P47's five-probe acceptance schema and cannot qualify P46 or any Lu process.

## Local verification

Python 3.13.5, Linux reference environment:

- Both focused P49 tests passed, including survivor detection and confirmed identity-stable cleanup.
- Entire P47/P48/P49 lifecycle-focused suite: **25/25 passed** (19 P47 + 4 P48 + 2 P49).
- `python -m cognitum.lifecycle_escape_negative` produced `boundary_gap_observed=true`, `child_survived_group_kill=true`, and `explicit_cleanup_reaped_child=true`.

Commands from an installed Cognitum checkout:

```bash
python -m unittest discover -s tests -p 'test_*lifecycle*.py' -v
python -m cognitum.lifecycle_escape_negative
```

The code exercises real processes in an isolated, fixed-function **reference** test. It does not execute arbitrary model-generated code, certify isolation, prove malicious-escape resistance, or run the missing P46 worker. The output is unauthenticated local observation, not host attestation.

## Corrective implications and remaining gates

1. **Do not treat process groups as a security boundary for untrusted plugins.** Linux execution will require an independently enforced and measured process-tree containment mechanism (e.g., appropriately delegated cgroup supervision plus user/mount/network namespace policy), verified against actual adversarial escape attempts and cleanup; selecting a technology does not itself complete verification.
2. P46 source recovery and independently measured OS evidence remain open. The P48 suite and P49 reference test do not authorize worker admission.
3. Windows AppContainer/LPAC, restricted-token, Job Object breakaway prevention, file/network/credential isolation, and Lu permission integration remain separate acceptance gates.
4. Keep general JSON repair, conversation authority, runtime orchestration, and Protobuf transport ownership in Lu. Cognitum implements only its independent capabilities, type-specific contracts, validation and tests; no Lu files are changed.

**Security disposition:** FAIL-CLOSED / DEMONSTRATED GAP for process-group-only containment; P46/Windows/Lu production acceptance unchanged and **not granted**.
