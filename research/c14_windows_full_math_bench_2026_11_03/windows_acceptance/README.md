# Cognitum C14 Windows mathematical benchmark — accepted

Date: 2026-11-03  |  Source: user-run v1.2 full Windows math benchmark

**Result: 113/113 scheduled portable checks PASS; 0 FAIL, 0 BLOCKED, 8 Linux-only unsupported.**

The benchmark executed **105 frozen-original-case MPFR proof replays at 224 bits**, checking **10,215 total nodes**. Eight mathematical test suites passed **91 test methods**.

## Original-case replays by phase

| Phase | Original cases | Nodes/case | Verified nodes | Aggregate task wall-time |
|:--|--:|--:|--:|--:|
| CH25 | 15 | 31 | 465 | 64.3 s |
| CH26 | 15 | 127 | 1,905 | 266.3 s |
| CH27 | 15 | 15 | 225 | 67.6 s |
| CH28 | 15 | 127 | 1,905 | 317.8 s |
| CH29 | 15 | 127 | 1,905 | 589.9 s |
| CH30 | 15 | 127 | 1,905 | 587.4 s |
| CH31 | 15 | 127 | 1,905 | 637.8 s |

## Historical mathematical test suites

| Suite | Test methods passed | Duration |
|:--|--:|--:|
| CH23 | 10 | 1.5 s |
| CH24 | 11 | 22.3 s |
| CH26 | 9 | 23.1 s |
| CH27 | 10 | 24.2 s |
| CH28 | 8 | 9.3 s |
| CH29 | 10 | 14.4 s |
| CH30 | 15 | 30.8 s |
| CH31 | 18 | 92.9 s |

## Scientific and engineering disposition

- All 105 original-data case/phase proof verifications returned `REPLAYED_BUT_UNRESOLVED`; these are *valid replays*, not successful global-optimality proofs.
- `CH32–CH39` journal/storage/OS identity gates were marked `UNSUPPORTED_PLATFORM` on Windows; they were not executed and must not be represented as passing.
- This benchmark covers the historical runnable mathematics included in the sealed CH23–CH39 archive; it does not establish coverage of every C14 mathematical function or recover unavailable earlier C14 source.
- The arithmetic implementations used across these historical phases are not all independent; CH40 is being developed to provide additional mathematical implementation independence.
- Report execution times are the sum of individual recorded task durations; do not interpret them as controlled phase-performance comparisons or elapsed wall clock for the entire bench.

Unmodified CH39 source archive SHA-256: `9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b`

Uploaded original Windows summary SHA-256: `0890434169666323c75a83131e7fd83ccae56fde1d5d1e4f1fefbc7fbe218bf6`

**Certification: historical portable mathematical replay ACCEPTED; scientific global-optimality NO-GO.**
