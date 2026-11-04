# CH40-M.3 — native library execution and acceptance (2026-11-03)

**Research engineering gate PASS_PARTIAL_NATIVE; C14 scientific release NO_GO.**

Verified the user-supplied package archives against upstream-pinned SHA-256 member checksums and ran isolated native Linux wheels without changing system Python or Lu. Original immutable CH23/CH40-K 15-case trace hashes were checked in each math harness. Scope: Python 3.13.5 Linux x86-64, python-flint 0.9.0 / bundled FLINT 3.6.0, PySCIPOpt 6.3.0 / bundled SCIP 10.0.2.

- Arb 256-bit Firth **point enclosures**: 15/15 overlap independently recomputed rational/Decimal point intervals. These are feasible-point statements, **not global bounds**.
- Arb conservative **terminal-region** direct-likelihood/Fisher-Hadamard upper bounds: 15/15 high-cap leaves conservatively agree with independent rational recomputation. No Arb result tightened a frozen historical strongest upper cap; direct naïve interval matrix det crossed zero for all 15 tested leaves, so only the mathematically justified Hadamard path was admitted.
- Paired original-leaf kernel timing: Arb 0.15450 CPU seconds total vs rational/Decimal 6.38068 CPU seconds, ratio ~41.3x. Conservative Arb caps are ~2e-9 to 5.8e-8 looser than the reference. This is **not whole-solver speedup or exact algorithm/precision equivalence**.
- Native SCIP original nonlinear expression expanded excessively and was OOM-killed. Replaced with compact auxiliary-variable model. Under 1.5 s solver-time/case, 512 MiB SCIP memory, 1.4 GiB process address-space and 12 s wall watchdog, all 15 actual original models ran. Three yielded feasible proposals, all three were independently checked with Arb and rational reference. No material feasible improvement >1e-8 over original incumbents. No SCIP-reported dual bound was promoted to an interval/global proof.
- IBEX 2.9.1 source SHA verified; CMake Filib/no-LP configure blocked before build because Flex and Bison are absent from this Linux container. Fifteen previously generated Minibex source models remain unparsed by native IBEX; zero IBEX certificates accepted. Official installation docs confirm Flex and Bison prerequisites.
- Ipopt 3.14.20 conda-forge Linux binary extracted; its runtime loader reports missing `libspral.so` and `libdmumps_seq.so`. cyipopt remains source-only; zero native Ipopt C14 experiments accepted.
- Local regression 8/8 pass with original frozen fixtures/native wheels; 3/3 isolated HTP downloader offline tests pass. No C02/C04/Lu permission change.

Research sources and selected evidence records are tracked under `research/ch40m3/` (including the Windows download-only HTP tool for checksum-pinned Debian Flex/Bison binaries). The external 800 MB original traces, prior CH40-J signed chain, 20/135 MB upstream wheel archives and downloaded IBEX/Ipopt binaries are **not duplicated** into Git.

Conversation package: `Cognitum_CH40M3_Native_FLINT_SCIP_All15_Research_2026-11-03.zip`, SHA-256 `be93c0ec8271ec90821a058fe6e978f3739aa30b4b017d98ef14964fb0653778` (55,455 bytes). HTP-only helper ZIP SHA-256 `545fb11d8095e50e9c5d8024311e727895920da5c6cc8bd6737bb9ab55f69bf2`.

**Required next work:** obtain checksum-pinned Linux Flex/Bison executables; compile/test IBEX parser on the 15 frozen Minibex models with verified interval engine; resolve a complete Ipopt native dependency set; run matched CPU/RAM incumbent and upper-bound benchmarks with independent proof checks. The 0.05 finite-root certified gap remains open. No unrestricted global optimum or causal identification claim is permitted. Existing signed research artifacts remain immutable.
