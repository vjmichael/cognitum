# MEL-07A-R1 — CPU evidence reconciliation and expansion

## Accepted baseline

Exact source `71050d284fd7678a8ab9c1ffe5f94d7b34c4afef`; [CPU Python 44663655326](https://github.com/vjmichael/cognitum/actions/runs/44663655326) and [integration 44663655236](https://github.com/vjmichael/cognitum/actions/runs/44663655236), 12/12 jobs. All four downloaded archives independently SHA-256/CRC verified; report source SHA and PASS, ten workload cases × three repetitions per host, 120 admitted and 840 direct timing samples, all routing and independent numerical controls passed. Identical direct/worker bytes within each repetition/host; ten request digests stable across hosts, two small VFA result digests vary across OS while remaining within tolerance.

| Native hosted target | Artifact ID | SHA-256 |
|---|---:|---|
| Linux 3.11 | 14596985881 | bbccb751bd95d4f53215dde8a0fa18dd364f67738278e76d0a6279c836a8edf8 |
| Linux 3.13 | 14597405322 | 1716c4a243b12dcaef9ae84e1df14c5838cca53d4744fd77529fd86a473b8c77 |
| Windows 3.11 | 14597540325 | 538a07e29071936a699c16e98c2402a72f8f290456a8ef9c53236ef223218e6f |
| Windows 3.13 | 14596422437 | 5a2b9a23bb71e1dcb10098464f291927b34ea39646b427a56555f51146405d22 |

| Target | Median direct per-case median ms | Median admitted ms | Median verification ms | Median worker share of prepare+admit+verify | Parent lifetime peak MiB |
|---|---:|---:|---:|---:|---:|
| Linux 3.11 | 0.58779 | 187.56556 | 5.69329 | 94.93% | 65.64 |
| Linux 3.13 | 0.64458 | 209.09611 | 6.47148 | 94.80% | 71.73 |
| Windows 3.11 | 1.4522 | 412.4638 | 12.5705 | 94.78% | 51.12 |
| Windows 3.13 | 1.3997 | 452.97405 | 12.08705 | 95.58% | 59.41 |

HDC exact; maximum scalar oracle difference VFA value 2.220446049250313e-16, gradient 1.1102230246251565e-16, KAN 1.1426903046007908e-7. Worker/admission dominates for these fixtures, not an isolated measurement of launch cost; medians of admitted/direct ratios 283.2–328.6. Linux reaped child CPU median 0.185741 / 0.207087 seconds; largest reaped child high-water same reported values as parent on these runs, not simultaneous tree memory. Windows child CPU/working-set absent. Different hosted hardware, runtime and OS; not a controlled Windows/Linux hardware comparison. No energy measurements.

## R1 extension (native execution pending)

- Keep CPU routing inert and default-off. Polynomial selection requires explicit research and polynomial opt-ins. Tensor/symbolic selection requires exact existing two-descriptor set and installed factories. Tensor selection checks are a separate review; actual COG-04N admission remains its own established gate.
- Existing polynomial KAN runtime: two sizes, orders 0/1/2, three repeats; 18 real worker calls and 126 warmed direct plugin samples. Same-host exact bytes, receipt replay, exact analytic x² / 2x / 2 fixture over represented dyadic points, absolute difference <=1e-12; existing certificate tolerance 1e-6 unchanged. Retain Protobuf requests/results and checkpoint.
- Matched VFA batching: four points in a single existing admitted request versus four individually admitted requests; three alternating-order paired trials. Each arm must complete actual workers, verify all outputs using existing certificate gate and match independent Gaussian values and each other within 1e-10. 15 total actual calls. Include preparation/grant/worker/verification within measured arm; no mandatory speedup threshold; this is an amortization experiment, not a custody bypass or new persistent worker.
- Fresh J/K/L fits using accepted COG-04N benchmark: real tensor/symbolic residual and integral through existing admission/Runtime; independent exact certificate and separate numerical replay, 5+5+6 actual calls, native traces and original request/result artifacts. Measure total including fitting and evidence and existing per-case totals; retain individual Runtime latency. Initial fitting is not isolated from overall elapsed.
- 49 additional actual calls per host (196 across matrix), 504 polynomial direct timings plus baseline rerun. Same four Python matrix jobs and existing full integrated regression. Whole R1 evidence SHA-256 map. No broad model or hardware promotion. Current implementation is pending native acceptance; local full source checkout not available. No Lu integration changes. Windows worker-specific resource measurement, broader complex workload and persistent process optimization remain open. Reproduce `python -m tools.mel07a_r1 --out mel07ar1-evidence` from a clean source checkout with existing scientific dependencies.

## Accepted R1 native results

Exact tested source `21fc878eb7cbe4b3c0163f4ad18bbecd1861e925`, [Python/CPU 44664652451](https://github.com/vjmichael/cognitum/actions/runs/44664652451) and [integrated regression 44664652419](https://github.com/vjmichael/cognitum/actions/runs/44664652419), all twelve jobs successful. Eight archive SHA-256 checks and CRC checks succeeded. All eight source SHA/status records match. Each expanded archive has 106 hashed internal files (424 total); no unlisted payload files. All polynomial and batching request/result hashes and tensor receipt pairs were independently checked against retained bytes. All 64 tensor/symbolic trace entries match scope-bound receipt operation and request identity and checkpoint hash. Mathematical replay was performed by the native gate; closeout did not re-execute each kernel locally.

| Target | Artifact (R1) | SHA-256 |
|---|---:|---|
| Linux 3.11 | 14597571537 | 6c2b6d1479e61cb0f218a076934cdef50f1be545e20e42f552416c35e9edc02b |
| Linux 3.13 | 14597411934 | 891d66d8e1f6b32f263baec9a486441226a4c86814fd85762e3b1d6b86ba763c |
| Windows 3.11 | 14597886193 | 9addaced28b8c5c03f3fb81262d90e7d092dc8e53794158fbb25448e896d3580 |
| Windows 3.13 | 14597836480 | 04bafc794dbc43fca0046ac1cb4cfdb9143fb8c6c436d69904fe604642bc8abb |

| Target | Artifact (baseline rerun) | SHA-256 |
|---|---:|---|
| Linux 3.11 | 14597047736 | 2799ffc99ff3fb322488ea882cd4e78b18d7d20ea0222adc60aac113dd937674 |
| Linux 3.13 | 14597576724 | b31a1e80f002dea62387c79403db4cfbbe1d83b5ddc3b3c1a1fdeabe794f112b |
| Windows 3.11 | 14597456946 | 1bacc6e8528c58bdec48b8eaec156e2ef51f65d3990a0863c655fb35c90a9e60 |
| Windows 3.13 | 14597891293 | 6249e9d2ccde01fe19d54e3800f810bd098e52b5a4c1d3b6b6205dcab8368f87 |

| Target | Batch median ms | Serial median ms | Median paired ratio | Polynomial direct median ms | Polynomial admitted median ms | Tensor fit+execution+evidence total ms |
|---|---:|---:|---:|---:|---:|---:|
| Linux 3.11 | 528.808 | 2100.664 | 3.9328 | 1.500 | 513.794 | 18832.96 |
| Linux 3.13 | 505.954 | 1983.678 | 3.9207 | 1.484 | 486.893 | 16498.00 |
| Windows 3.11 | 571.732 | 2380.538 | 4.1637 | 1.112 | 569.979 | 19117.18 |
| Windows 3.13 | 713.468 | 2786.743 | 3.9740 | 1.632 | 679.689 | 20240.48 |

Batch and serial medians are separate; ratio is median of individual paired ratios, not necessarily their quotient. All 12 pairs matched numerically exactly; observed ratio range 2.5439–4.3422. All polynomial analytic x²/2x/2 fixtures had zero observed error, not a universal KAN accuracy conclusion. Maximum tensor represented numerical residual oracle difference 1.452830911130576e-16; the certificate solution error bounds are distinct. Native baseline 120 admitted calls and 840 direct samples plus R1 196 actual calls (72 polynomial, 60 batched/serial, 64 tensor/symbolic) and 504 direct polynomial samples. These counts exclude separate refusal and regression checks. Hosted results only; Windows child CPU/RSS remains unmeasured, no comparable power or physical platform conclusion. Artifacts are subject to hosted retention. Preserve scope boundaries and prioritize batching before redesigning worker lifecycle.
