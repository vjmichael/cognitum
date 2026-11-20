# COG-05B — Reproducibility preflight and native-kernel experiment design

Status: accepted for **local isolated reference preflight and experiment design only**. No new native backend or full portable environment qualification. Accepted scientific source remains `826e4b9459e4b70413ef8f0813a4c41c2b609fae`; COG-05A accepted at `b96c0dbe06bef0bd5aaf9832041cbaf2dee76ce8`. All prior kernels and workflows unchanged. See [frozen protocol](PROTOCOL.md), [isolated executable reference](../../../tools/cog05b/reference.py), [COG-05A evidence index](../cog05a/REPORT.md).

## Actual local execution

Hosted Linux x86-64 Debian 13.3, AMD EPYC 9V74, one logical CPU affinity, cgroup CPU quota 4 CPUs and memory limit 4 GiB (not a physical-machine benchmark). System CPython 3.13.5 with isolated/no-site mode (`-I -S`), no third-party Python dependencies. Executable SHA-256 e59d0124ff06c248546876e01fcfb1ea3cda63534949f94a9372bfcfe3bfc3f5; 615 stdlib Python source files manifest SHA-256 29b2aea3fac7a206151d52e0bc5de47ad50fdb22000f7f40efdff7ebb3d169da. Debian python3.13/minimal/libpython3.13-stdlib 3.13.5-2+deb13u4, libc6 2.41-12+deb13u3. Observed, not used to build a kernel: GCC g++ 14.2.0 (Debian 14.2.0-19), Boost 1.83, GMP 6.3.0. No package installation.

Four U archives independently rehashed (14605961982, 14606630117, 14606755233, 14605736313) against original archive SHA-256, CRC checked, source and PASS verified. All 24 matrices byte-identical across the four targets and receipt digests matched. Independent Fraction polynomial reconstruction generates complete canonical mass/stiffness and exact LDL receipts solely from coefficients and knots, not from archived results. 6 fresh subprocesses x 24 inputs = 144/144 SHA-256 output matches. Altering one expected digest caused a nonzero exit with exact output mismatch. This is a trusted-fixture diagnostic control, not a fully validated general input interface; no independent new theorem review or accepted R/U module execution in this experiment.

| Route | Three CPU samples (ms) | Median CPU (ms) | Median full launch elapsed (ms) |
|---|---|---:|---:|
| Dense reconstruction | 2062.020, 2111.052, 2065.199 | 2065.199 | 2110.370 |
| Support-aware reconstruction | 340.138, 352.187, 325.921 | 340.138 | 379.765 |

Median-of-arm ratio 6.0716467861x, not a native-language speedup. Full 24-matrix assembly + LDL + serialization; excludes input read/parse, output digest verification, imports and startup. RSS pre-solve 13.805–13.812 MiB, post-solve 14.520–14.535 MiB; OS lifetime peak 21.621 MiB for every subprocess, possibly includes inherited high-water from fork/pre-exec. No demonstrated peak advantage of support-aware over dense. No directly comparable claim against the larger SciPy-based accepted process. Cold-launch timing includes subprocess overhead and verification. Three exploratory pairs only.

## Reproduction custody

- Independent script Git blob `579aeb76db38613ab2c47765f3df07d1f3e1a8de`, SHA-256 `84f371034f10f4b5352c160df890656808d0993c91ffb91364f72acb53935165`.
- Frozen 24-case corpus SHA-256 `a6a353adb4190529c22291f98f7dd0b96ee59b16b141d48fc04e042a1dcd2c8d`.
- Environment JSON SHA-256 `926e72a015e41c0695b8a2a9f50eb83119132ea961358ae0840be72102d0e229`.
- Raw results JSON SHA-256 `815c3ab0df1335dcdb8fd8ca484998d4e381a91138df88ad9daf91ad0fa1cad0`.
- Host package/library fingerprint SHA-256 `8a9197f72aaf411bbc6478551b2e01d32ca2b125448070e2aedcf934fcb8c2e8`.
- Portable evidence package delivered separately in owner conversation: Cognitum_COG-05B_reproducibility.zip SHA-256 `dbdae0dc9a4d96f2626fb8bf23924720c2c67ecf6336e572fd2869c2255a0076`. Includes exact executed script, protocol, original four U archives, frozen corpus, raw six samples, environment/host records and rejection log. ZIP CRC checked. Does not include interpreter executable or OS snapshot. The corpus is reconstructible from original archive bytes; no GitHub artifact expiry guarantee.

Run from repo root: `/usr/bin/python3 -I -S tools/cog05b/reference.py run Cognitum_COG-05A_evidence.zip NEW_OUTPUT_DIR`. A future full experiment must use real accepted R/U kernels as primary controls, separately freeze held-out and invalid inputs, supply independent mathematical verification, lock the full OS/compiler/dependency environment, and record matched physical and Windows measurements. No native implementation, production promotion, language selection, FPGA or Lu work authorized.

Next proposed COG-05C — prepare and qualify frozen conformance/held-out corpus and clean restoration of the matched accepted-Python and selected native toolchain environments before any native implementation.
