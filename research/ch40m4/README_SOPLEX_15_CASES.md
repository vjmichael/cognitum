# Cognitum CH40-M.4 — actual native IBEX smoke and first 15-case optimization baseline

**2026-11-03 / Debian 13 Linux amd64 / research-only**  
**Engineering: native build PASS; 15/15 native C14 optimizer invocations RETURNED_BOUNDS.**  
**Mathematical: 0/15 reach 0.05. Scientific C14: NO-GO.**

## What was really executed

1. Validated uploaded official `ibex-team/ibex-lib` v2.9.1 source archive against upstream SHA256 `b3cd09c3be137fd2ff0f2570c3bcbdfcd9ea62fcf04d45d058db3b0dbb1d8872` and the uploaded Debian 13 Flex/Bison SHA manifest. Unpacked both within an isolated working directory, without host package installation.
2. Built **IBEX 2.9.1 + Filib 3.0.2.2 + no LP**. Native `ibexsolve` parsed/executed all 15 generated frozen CH23 C14 Minibex cases. This is a **constraint/parser gate**, not optimization.
3. Built **IBEX 2.9.1 + bundled CLP 1.17.6**, but `ibexopt` crashed in `CoinIndexedVector::~CoinIndexedVector()` on both a tiny quadratic and an official nonlinear example. Those outputs are **rejected**. See `results/CLP_BACKTRACE.log`.
4. Built **IBEX 2.9.1 + bundled SoPlex 4.0.2** after a local extracted-copy C++ portability fix (`primes = base.primes;` is invalid array assignment; copy its 50 elements explicitly). The **upstream source ZIP was never modified**. Tiny quadratic optimum and official Hock–Schittkowski nonlinear example both solved; see logs.
5. Ran `ibexopt --timeout=1 --simpl=0 --abs-eps-f=0.05` on all 15 hash-pinned original CH23 Minibex models. **15/15** returned program-reported optimization intervals; **0/15** achieved 0.05. Gaps range **41.2381143 to 265.2372301**. Model expansion/parser overhead adds ~3.5–11.2 seconds wall time beyond the 1s core solver budget. This is **not** a CPU-matched or independently certified global-proof comparison against CH40-L.
6. Increased optimizer time to 8 seconds on two cases: `zero_balanced_n80_i00` gap **41.23811 → 41.09448**; `quasi_separated_n160_i00` gap **265.23723 → 259.37593**. Both stopped on time limit.
7. Independently **point-evaluated** the 15 *printed, rounded candidate coordinates* through FLINT/Arb at 256 bits, with rigorous Fisher-determinant enclosures. On two representative cases (`zero_balanced_n80_i00`, `quasi_separated_n160_i00`), a separate rational/Decimal point evaluator overlapped the FLINT intervals. These checks validate point objective enclosures **only**, not native IBEX global caps.

## Reproduce

Requires two existing external source packages: `Cognitum_IBEX_Source_Repair_20261103.zip` and `Cognitum_IBEX_Flex_Bison_Debian13_Offline.zip` from `/Cognitum/Packages`. Requires Debian 13 Linux x86-64 with CMake, Ninja, GCC/G++, m4, Python3, and `dpkg-deb`.

```bash
bash source/build_offline_ibex.sh /path/Cognitum_IBEX_Source_Repair_20261103.zip /path/Cognitum_IBEX_Flex_Bison_Debian13_Offline.zip /tmp/ibex-test
python source/run_native_ibex.py \
  --ibexopt /tmp/ibex-test/build/bin/ibexopt \
  --frozen-model-zip evidence/CH40M2_MODEL_PINNED_INPUTS.zip \
  --workdir /tmp/ibex-native-results --solver-seconds 1 --wall-seconds 28
python -m unittest discover -s source -p test_evidence.py -v
```

The 400 KB `evidence/CH40M2_MODEL_PINNED_INPUTS.zip` is the **actual previously frozen CH40-M.2 archive** containing 15 original model expressions, not synthetic replacements. Each `.bch` model was SHA-256 matched to that archive before running.

## Scientific limitations

- A solver's displayed `f* in [lo,hi]` is **not** accepted as a CH40 proof witness until separately independently checked using rigorous interval rules and the identical objective/parameter domain.
- The current unoptimized interval model contains dozens/hundreds of repeated `exp` and Fisher `log(det)` expressions. Very wide intervals are expected from dependency overestimation and poor global branch search on a one-second budget.
- Never add/subtract these native IBEX objective gaps directly to previous CH40 finite-root original-producer certificate gaps. Proof domains, rounding rules, and full effective budgets must be aligned first.
- The 0.05 target is still open for every case. No unrestricted global optimum, causal effect identification, or scientific C14 release is established.
- `ibexopt` with SoPlex is a **working experimental baseline**. The bundled older SoPlex required a **local build-only** compiler compatibility patch; security, packaging, binary license obligations, and repeatability on Windows remain unqualified.
- Native IBEX's CppUnit test target was unavailable: the environment lacked the CppUnit development library; this report relies on real model execution and the two known-good solver smokes, not a claim of IBEX's full upstream test suite passing.

## Next engineering work

Change the mathematical *formulation* before spending much more CPU: reduce expression duplication (shared Fisher terms), factor/reparameterize logdet terms, apply contractors, and compare IBEX/Arb bound quality on **identical CH40 terminal boxes**. Use strict independently certified bounds and equal CPU/memory controls; preserve all CH40-J signed sources unchanged.
