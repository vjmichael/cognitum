# Cognitum P48 — Linux reference-native lifecycle probes

**Date:** 2026-10-31  
**Scope:** Cognitum only. Local-first development; GitHub is source control and the milestone ledger, not the development hub.

## Checkpoint boundary

The full P46 direct-worker parent-lifetime/fault-matrix source checkpoint remains unavailable in the inspected repository and accessible local/Library files. Historical P46 reports therefore have not been reproduced. P48 deliberately implements a **separate fixed, trusted Linux reference fixture** and exports a receipt compatible with the P47 structural validator. It does **not** claim to run, replace, validate, or approve P46 or arbitrary Cognitum extensions.

The reference runner is at cognitum/reference_lifecycle.py; developer-only CLI at tools/run_reference_lifecycle.py; adversarial tests at tests/test_reference_lifecycle.py. It does not change Lu.

## Five real-reference process observations

1. **supervisor-death-idle:** Fixed worker installs Linux PR_SET_PDEATHSIG=SIGKILL, verifies its expected parent PID, announces readiness, and is observed to die when the supervisor is killed. The observer reaps the adopted child and verifies a SIGKILL exit.
2. **supervisor-death-launch-race:** The fixed supervisor is held at an explicit prelaunch barrier and killed before a worker can start. A zero worker PID is recorded.
3. **supervisor-death-midflight:** Worker is ready and active when the supervisor is killed; observed exit and reaping are checked.
4. **cancel-with-descendants:** A newly created private process session contains the worker and its subprocess. The runner kills exactly that session process group, reaps both processes, and tests for survivors.
5. **output-pipe-backpressure:** The worker fills an unread Linux pipe while alive; the test checks that unread bytes reach actual pipe capacity, then terminates and reaps the worker.

A Linux child-subreaper is required for adopting and waiting on orphaned child processes. Fixed test processes install a parent-death check where appropriate. Subprocess pipes are explicitly unbuffered so the readiness handshake is not hidden by Python BufferedReader prefetching. The runner bounds readiness and cleanup waits. Its process-group signals are scoped to fresh process sessions.

## Local-only verification

On Linux, Python 3.13.5, the focused P47/P48 suites were run with **23 tests passed**: P47's 19 existing structural tests and four new P48 tests. A direct reference run observed five of five probe cases with a P47-structural PASS. Three independent five-case reference runs passed after correcting a too-short two-second child-startup window. The final guarded fixture also passed its direct run and focused regression suite.

The negative control removes the worker's parent-death signal and confirms that the unreaped survivor is reported as a failure before forced cleanup. A separate injected-probe fault must yield FAIL, and a wrong expected source digest yields INVALID. During development, this test suite caught both buffered readiness and delayed reaping after cleanup; both were corrected.

Run from repository root:

    python -m unittest discover -s tests -p 'test_*lifecycle*.py' -v
    python tools/run_reference_lifecycle.py --out p48-reference-receipt.json
    python tools/verify_lifecycle_evidence.py p48-reference-receipt.json --source-sha256 EXPECTED_SOURCE_SHA256

For EXPECTED_SOURCE_SHA256 calculate the exact SHA-256 of cognitum/reference_lifecycle.py from the checked-out source and independently compare it. Local checkpoint source SHA-256: **a3cb261e1f9756ef2ff6a80ab7cc122574d3bb186209115cb2c0cfabfb741ffd**. The expected digest is not an authentication credential.

## Important exclusions

- The receipt is **locally self-reported and unauthenticated**. A structural PASS is not independent OS attestation.
- This tests **only a reference fixture, never P46's unrecovered worker**. It does not establish Windows compatibility, Lu-native integration, AppContainer/LPAC confinement, Windows Job Objects, network denial, credential isolation, handle inheritance controls, malicious escape resistance, or a signed-grant security boundary.
- PR_SET_PDEATHSIG alone does not kill arbitrary descendant trees; process groups are not sufficient protection against hostile breakaway. A Linux process can exit and still require reaping. The reference experiment does not make production worker admission safe.
- **Cognitum native CE admission remains default denied.** No Lu source or runtime changes are authorized.

## Next gate

Recover P46's complete source archive, verify its original digest and traceability, replace the reference fixture with actual P46 execution while preserving independently measured PID/exit/cleanup evidence, and rerun failure, survivor, and escape cases. Windows x86-64 containment and Lu authorization remain separate hard gates; do not infer them from Linux structural receipts. ON/OFF LLM evaluations remain independent work.

**Repository policy:** develop and test locally, publish reviewed source and explicit test evidence in coherent checkpoints, and use GitHub Actions sparingly as secondary verification rather than gating local progress.
