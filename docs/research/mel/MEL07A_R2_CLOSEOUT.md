# MEL-07A-R2 — exact-source acceptance closeout

Accepted scoped reference source `df432b9636a5046971486786ae3fe2bf7748744d`, November 19, 2026 Arizona local. [Python and CPU benchmark](https://github.com/vjmichael/cognitum/actions/runs/44666754286) 4/4 and [integration](https://github.com/vjmichael/cognitum/actions/runs/44666754114) 8/8; 12/12 successful. This documentation-only closeout does not claim another tested source SHA.

Four R2 archive digests and ZIP CRCs independently verified; all 1,712 internal file hashes, 856 request/result pairs, 856 native telemetry records and 104 paired comparisons reconciled against retained R2 reports. Each target has 52 arms, 26 pairs, 214 real worker executions, 428 retained protobuf files; all reports bind the exact tested source and PASS. Per-call byte counts/hashes, unique request artifact identity within each archive, measurement status, sample count, CPU nonnegative finite, peak positive, and arm CPU sum/maximum observed peak checked. Both refusal controls present in every report. Independently recomputed every reported paired speedup and paired value difference from retained measurements/outputs. Native CI ran independent mathematical verification; this closeout did not independently rerun every numerical kernel. Prior MEL-07A and R1 rerun jobs passed; their separate archives were not independently rehashed in this R2 audit.

| Target | R2 artifact ID | SHA-256 |
|---|---:|---|
| Linux 3.11 | 14597849308 | cd8a62dc586a9d94a649cc94b76518ac669a01b0d8dacf3d18382d8a90705bc3 |
| Linux 3.13 | 14597369928 | b128216f4e7460158a9def5ed447c920c4555ce5aa617a25a6233da67cf2b30a |
| Windows 3.11 | 14597559987 | 8f3c48b92032881836d68d6acdef15bd1ce538676a7faf4526b7a4a752a93521 |
| Windows 3.13 | 14598955050 | 4d43d5e27a54ce030d663cc705d85a840a7b8b2d5d99ba9510f72291d10257e2 |

| Target | Range of measured paired speedups (all sizes) | 16-row VFA value median | 16-row VFA gradient median | 16-row KAN median | Median observed worker CPU seconds | Maximum observed worker peak MiB |
|---|---:|---:|---:|---:|---:|---:|
| Linux 3.11 | 1.933–15.952 | 15.670 | 15.780 | 14.982 | 0.2900 | 63.97 |
| Linux 3.13 | 1.948–15.892 | 15.681 | 15.673 | 15.228 | 0.2400 | 71.05 |
| Windows 3.11 | 1.908–15.571 | 15.523 | 15.407 | 14.704 | 0.3281 | 48.86 |
| Windows 3.13 | 1.860–16.455 | 15.956 | 15.905 | 15.035 | 0.2812 | 57.01 |

All 104 batch/serial comparisons had zero observed difference. Maximum independent analytic oracle difference across arms 1.1426903046007908e-7 (within existing KAN tolerance). All Linux CPU and memory observations are sampled lower bounds, not complete process totals; Windows CPU final after termination, peak working set observed lower bound. No tree-wide memory, energy, physical hardware comparison or universal optimal batch size claim. Results are for bounded homogeneous fixed fixtures, not arbitrary production workloads; instrumentation is opt-in and not a custody/security guarantee. Exact frozen worker, Runtime and Trace unchanged.

Both Linux and Windows 3.11.18 x64 standalone archives are now listed in Shared Development Toolchain; the Windows upload is not established as having been executed on a native host by this gate (hosted Python 3.11 acceptance is distinct). No new downloads requested.

Next proposed task MEL-07A-R3: resource-aware bounded CPU batch sizing on existing eligible homogeneous typed workloads, with no merging of unrelated requests or scopes, no new grants or bypass of verification, matched accuracy and measured CPU/memory/time limits. Persistent workers remain a separate conditional research experiment. Lu remains deferred; no GPU route or production promotion.
