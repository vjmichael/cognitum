# COG-05-SSM-07 — Learned state-space mathematical foundations

**Status:** bounded CPU research candidate. 34/34 dedicated tests and 240/240 available combined local tests passed. Native acceptance pending. Parent 6d62b8a7a7c447b47cbb992e8a8986ecb3d821f5. No new dependencies or execution authority.

## Mathematical scope

- DS49: online normalized shifted-Legendre (LegS) history projection for piecewise-constant samples with positive irregular durations. Projection updates transform the existing coefficient vector into the expanded time window and add the new interval integral via Gauss–Legendre polynomial quadrature. Tracks mean-square truncation error using cumulative energy. Independent adaptive quadrature verifies coefficients and errors at multiple orders. Numerical reference, not an exact-rational implementation or general continuous interpolant.
- DS50: dense real/complex MIMO LTI state recurrence and explicit impulse response convolution with nonzero initial-state response. Stable real diagonal recurrent pole and readout fitting via bounded nonlinear least squares with analytic Jacobian against central finite differences. Three independently seeded synthetic identification cases and unseen input sequences. Not a general nonlinear architecture or validated recovery of historical trained checkpoints.
- DS51: LegS HiPPO initialization, normal-plus-rank-one decomposition with unitary complex basis, equivalent DPLR matrix, bilinear discretization via rank-one Woodbury inverse, and dense-reference parity. S4-inspired reference recurrence and trainable readout on fixed features. No full S4 block, Cauchy/FFT fast kernel, end-to-end structured transition training or performance claim.
- DS52: stable complex diagonal continuous rates with exact-ZOH mathematical update, variable positive step, complex-conjugate fixture yielding real outputs, long-memory decay reference, and fitting readout on fixed diagonal features. S4D/S5-style mathematical primitive, not complete DSS, LRU or production S4D; baseline comparisons, broader stability and training still open.
- DS53: diagonal affine associative scan using parallel doubling, verified against serial recurrence for lengths through 512 and complex MIMO irregular-step matrix exponential reference, with carried state across chunks. This NumPy reference is not a parallel GPU kernel. Scan gradient and full S5 architecture training open.
- DS54: bounded single-input selective recurrence with causal convolution and input-dependent delta (softplus), B and C; exact ZOH input integration for held input; scan/serial parity and future-input perturbation causality checks. This is a selective SSM foundation and not a full Mamba-1 block; original Mamba input discretization, gated residual stack, parameter training/gradient and multi-channel comparison remain open.
- DS55/56 remain open: SSD / Mamba-2, Mamba-3 and adjacent recurrence families.

All six rows DS49–54 remain PARTIAL. DS49, DS51–54 newly initiated. 61 partial, 11 open of 72. No inference-speed, benchmark superiority, deployment, general model equivalence, or control authority asserted.

## Actual local evidence

Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2; one-thread BLAS/OMP/MKL. Dedicated 34 tests passed in 0.55 s. Initial combined collection failed because the previously staged KAN test imports the absent tools.cog04o fixture package. Re-ran with that integration file explicitly excluded; 240 available tests passed in 3.05 s (206 inherited + 34 new), no failures/errors/skips in that run. Prior KAN integration and full native/regression qualification remain outstanding. Timings are test durations only.
- Source Git blob 6830e8324ca80108074a23b553529776d812b34e; SHA256 ab4314ba35f2c7f7fcd8a4a6d2830dfb14648c338a9e8e11492a5d2f3af1bc7f.
- Test Git blob d31c1420820ef4977cdb839b8645905295b5396c; SHA256 a37047cf35d6ac3d953b632b571687262359f26a06c2c4536a3ceaf6c111a311.
- Dedicated JUnit SHA256 9578ae28102c7652ed68b090aad5804f9ed30df24ca514b174b27f3ba44bc50b.
- Combined JUnit SHA256 8eef7d1c3ebe17ab13cfff3f56c39cec47fe62651c75a5b0cd777ba29fadfbb8.
Published source and test blob IDs match locally tested bytes. Small CPU fits: three nonlinear pole/readout trials with held-out RMSE <1e-8 and Jacobian parity <1e-6, two fixed-structured-feature readout trials with held-out RMSE <1e-10. This is numerical synthetic evidence, not end-to-end trained S4/S5/Mamba comparison.

## Native and next development
Sequential same-head gate consumes SSM-06-R1 receipt (31 cases), validates cumulative source pins and prior artifact hashes, runs 34 dedicated cases and preserves receipt/log/XML. No overlapping CI initiated; existing candidate branch retained, main unchanged. Prior KAN and native closeout remain required.
Next independent SSM-07-R1: trainable structured and selective sequence references, scan gradient parity, Mamba-1 discretization, Mamba-2 SSD semiseparable/block equivalence, generalized complex/rotation and MIMO recurrence profiles, stable parameterization, recall and permutation negative controls; explicitly distinguish mathematical references from complete architecture implementations and keep production integration deferred.
