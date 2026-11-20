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
