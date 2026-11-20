# MEL-07A-R3 — resource-aware CPU batch sizing

## Scope and evidence

R2's accepted 856 worker observations and 104 paired trials showed substantially amortized overhead, not a universal optimal batch size. Across hosted Linux/Windows, 16-row VFA/KAN batch medians are roughly 270–383 ms; observed worker peak working set/high-water memory roughly 49–69 MiB in those batch cases. Different hardware, fixed fixture, no causal platform comparison. [R2 closeout](MEL07A_R2_CLOSEOUT.md).

## Implementation

`cognitum.mel.cpu_batching.plan_cpu` uses existing reviewed CPU selector, one validated typed VFA/KAN/polynomial/HDC query request and host-supplied scope/limit policy/calibration. Exact workload fingerprint binds operation descriptor, function or checkpoint, polynomial order/tolerance or HDC probe. Same function/checkpoint does not guarantee identical execution resources for different coordinates. No support for independent HDC binds, unrelated requests or multi-worker graphs. Native certified row caps: 16 VFA/KAN, 4 polynomial, 8 model HDC candidates. For at most 16 items, enumerate contiguous measured-size partitions only, with deterministic tie-breaks. Every child has a distinct derived ID and exact canonical request hash; enforce per-call profile, exact aggregate request bytes, reserve maxima for result bytes, total grant work and call count (repeated checkpoint computation charged). No new authorization. Model cannot choose profile, caps or allocate a grant. The planner is not a dispatcher or safety guarantee; the host must separately authorize exact child frames, preserve caller scope and enforce the actual existing grant.

Fresh R2 same-head/host calibration uses worst observed singleton per-worker latency+verification or amortized serial time, and full batch arm elapsed for measured larger sizes, maximum observed worker CPU and peak with a 25% heuristic margin. Bounds for these estimates are only planning targets; Linux observed CPU/RSS remain sampled lower bounds, Windows CPU final and peak working set lower bound. No enforcement of OS limits, no inference to a different host or hardware, no statistical confidence claim. Timing not guaranteed; never attribute zero memory or CPU to missing data. No unmeasured batch sizes estimated. No automatic cross-scope aggregation. No persistent workers.

## Qualification

Same-head R2 rerun in existing Python regression job followed by R3. Test synthetic constrained cases to validate deterministic policy and rejection, not performance. Five held-out homogeneous requests use different represented coordinates/candidate order and non-power-of-two sizes. Each adaptive, hard-constrained and singleton control runs actual existing admitted worker calls with one grant per arm, with independently verified results and independent analytic or exact bit oracle. Compare every component; preserve HDC global ties and row-major polynomial derivative output semantics. Record observed CPU/time/peak (not a hard ceiling), selected sizes, independent evidence and calibration digest. No mandatory speedup threshold; estimation error is a result. No native acceptance claimed for this candidate until four environments and consolidated regression pass and receipt evidence is reconciled.

No new packages; Lu remains deferred. Frozen Runtime/worker/Trace and all historical source pins unchanged.

Prepublication tightening: verify all 428 same-head R2 internal payload hashes, actual per-call request/result hash and size, decoded operation-specific profile fingerprint, count and ID before ingesting any measurement. Explicit trusted per-call planning cap applies to every engine, including polynomial. Estimate error reported separately against actual held-out measurements. Unit tests avoid reimporting benchmark environment setup. Candidate inspected, but no complete local repository checkout; native CI is the numerical execution gate.

## Accepted R3 native results

Exact source `cd3a215c27c7de50fe93b90acea9f206bbcb10d1`; [Python and CPU regression](https://github.com/vjmichael/cognitum/actions/runs/44668969288) 4/4, [consolidated integration](https://github.com/vjmichael/cognitum/actions/runs/44668969244) 8/8. Eight R2/R3 archives downloaded and independently SHA-256/CRC verified. Internal manifest equality and all 2,464 file hashes checked (R2 1,712, R3 752); all 1,232 retained request/result digest pairs and per-worker measurement records reconciled. Four same-head R2 reports bind the R3 calibration report digest; recomputed the 72 size-specific timing/CPU/memory estimates (18 per host) from their retained measurement rows, and all adaptive sums/maxima and actual-minus-estimate residuals. All reports bind exact source and PASS. R2 214 workers per host, R3 94 (18 adaptive, 27 constrained, 49 serial). All 60 held-out arms cover original item sequence, constrained partitions <=2 and singleton arms exactly one; all 20 per-host workload comparisons match component sequences exactly. HDC global tie indices independently recomputed from retained distances. Max reported independent analytic oracle difference 1.1426903046007908e-7, within KAN tolerance. Native gate performed mathematical verification. Closeout does not independently rerun the kernels or decode/replay every mathematical Protobuf witness. Prior A/R1 reruns passed in workflow; their eight separate archives were not rehashed in this audit.

| Target | R3 artifact ID | SHA-256 |
|---|---:|---|
| Linux 3.11 | 14598309505 | a8449e0fc2f6976860d33e8d4b371635f35864b1c33545e9c830e104f4100b60 |
| Linux 3.13 | 14599427446 | 3797d21efd4f6f686dee4a196eaa0019bd8027fd4a3a7a25a94fec7c8d6e3e01 |
| Windows 3.11 | 14599462559 | a06924f02a44a186015debfb7ca86fe212b9e7b08eba4e55f837e94e20f13f93 |
| Windows 3.13 | 14599535851 | aa2dfe2e193f7edf08413ed5d403a9d956d3cfe9a093913b08964c8471c56b75 |

| Target | R2 calibration artifact ID | SHA-256 |
|---|---:|---|
| Linux 3.11 | 14599502221 | 8603289d2314f4f657c6068e0b0e4a3ec0ca1456693507c859b686ec42ace598 |
| Linux 3.13 | 14599570335 | d4ebb9f2ce10aa45d34cd36f47b122f6cba68feef3eafe15d8a399abbb4c8929 |
| Windows 3.11 | 14598429514 | f205ab11d46310cc3720bc923d3bc199ee702b5dfc61d1f3850d12ea92698651 |
| Windows 3.13 | 14599575545 | a146677a495b5de1a019d31828e5c55a6d49fdd2458812849a1293a4ea51c760 |

| Target | Adaptive total ms | Constrained total ms | Serial total ms | Median adaptive/serial speedup (serial/adaptive) | Observed child CPU reduction | Largest adaptive worker observed peak MiB |
|---|---:|---:|---:|---:|---:|---:|
| Linux 3.11 | 4112.03 | 6149.78 | 11091.87 | 2.971 | 63.15% | 65.10 |
| Linux 3.13 | 6027.98 | 8980.80 | 16258.73 | 2.957 | 63.15% | 69.38 |
| Windows 3.11 | 6125.89 | 8915.84 | 16701.97 | 3.182 | 63.10% | 48.94 |
| Windows 3.13 | 8537.20 | 12878.11 | 23113.08 | 2.902 | 63.44% | 57.23 |

Each total sums five distinct held-out requests; not a replicated measurement of a single workload. Arm elapsed includes instrumentation, verification and evidence writes inside the timed loop, not just kernel compute. Median speedup is median of the five paired ratios (not quotient of total times). Across all 20 cases median 2.964, range 1.360–3.692. Adaptive beat serial 20/20 times and constrained 15/20; three larger VFA/KAN workloads on all four hosts benefit from the larger permitted sizes, while the polynomial and HDC partitions have identical batch-size counts to constrained and timing variation. Dispatches 72/108/196 respectively across adaptive/constrained/serial. Observed CPU reduction refers only to worker process CPU, not whole-system CPU or energy. Worker memory is largest observed individual peak, not a sum or machine RSS.

| Resource | Actual / estimate minimum | Median | Maximum | Overruns |
|---|---:|---:|---:|---:|
| Elapsed | 0.7065 | 0.7714 | 0.8545 | 0/20 |
| Observed worker CPU | 0.6750 | 0.7570 | 0.8087 | 0/20 |
| Observed worker peak | 0.7738 | 0.8004 | 0.8034 | 0/20 |

Planning estimates deliberately include 25% heuristic margin above observed maxima. Actual/estimate <1 on all 60 comparisons does not establish guaranteed bounds, population accuracy or safety under other load/hardware. Linux counters sampled lower bounds, Windows final CPU and observed peak lower bound; observed memory targets cannot serve as a hard RAM cap. Held-out coordinates/order differ but use same reviewed function/checkpoint/probe as calibration. No extrapolated general performance, statistical superiority over unmeasured partitions or production authorization. Tests did not compare all possible unmeasured batch widths. Source remains unchanged at closeout; previous exact SHA accepted within the scoped profile. Lu deferred; no new dependencies.
