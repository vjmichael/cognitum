# Library versus Cognitum GitHub: HDC/KAN/SSM recovery audit
Date: 2026-11-04
Status: initial source-gap audit based on visible Library folders and main/unified branch trees.
Not a claim that all user archives were exhaustively enumerated.

## Search coverage

Examined ChatGPT Library roots `/Zog Zoo`, `/Zog Zoo/zogzoo_hdc`,
`/Zog Zoo/hdc_backend`, `/Zog Zoo/benchmark`, `/torchHD-main/torchhd`,
`/pykan-master/kan`, `/Cognitum`, and `/Cognitum/Packages`;
crosschecked the Cognitum `main` GitHub tree and
`cognitum/unified-hdc-kan-ssm-20261101` branch.

The Library corpus is large and the broad recursive listing was incomplete;
the findings are **verified present/missing among inspected locations**,
not a guarantee no other private archives exist.

## Source gaps discovered

| Library evidence | Present in main before recovery? | Action / decision |
|---|---|---|
| `/Zog Zoo/zogzoo_hdc/models.py`: BSC, MAP, FHRR, HRR | **No**, only narrow BSC opt-in adapter | Recovered original file to `cognitum/research/hdc_recovered/` |
| `/Zog Zoo/zogzoo_hdc/memory.py`: Bank cleanup, BM25, rescore | **No** original full module | Recovered in isolated research namespace |
| `/Zog Zoo/zogzoo_hdc/sdm.py`: sparse distributed memory | **No** | Recovered as research; **not** a Lu ANSF canonical database |
| `/Zog Zoo/zogzoo_hdc/resonator.py`: factor recovery/resonator network | **No** | Recovered as research; no accuracy claim |
| `/Zog Zoo/zogzoo_hdc/quantum.py`, `stochastic.py`, `lowdisc.py`, `neuralhd.py`, `text.py` | **No** | Recovered for separate bounded evaluation |
| `/Zog Zoo/zogzoo_hdc/core.py`, `runner.py`, `selftest.py`, `metrics.py`, `parallel.py`, `dataio.py` | **No** | Recovered original experiment infrastructure |
| `/Zog Zoo/hdc_backend/torchhd.py` | **No** | **Not copied**: adapter assumes external TorchHD; integration and license/revision audit first |
| `/torchHD-main/torchhd` full third-party implementation | **No vendored copy** | Reference/external dependency candidate; do not silently bulk-publish |
| `/pykan-master/kan` KAN implementation and docs | **No vendored copy** | Reference/external dependency candidate; inspect license, version, resource/security model before optional connector |
| Uploaded `Zog_Zoo_HDC_KAN_K4_Optimization_Report_2026-10-25.md` | K4 optimizations **not verified restored** | Specifically audit optional packed BSC/MAP bank, corrected fractional-query scores, BM25 vectorization and optimized KAN inference against recovered snapshots |
| Uploaded `Zog_Zoo_HDC_KAN_Frontier_Review_2026-10-25.md` | Full breadth **not** implemented | Preserve roadmap: OnlineHD/AdaptHD/neural/quantized HDC, formula recovery, KAN training/baselines |
| Uploaded `training-an-ssm-detailed.md` | **No** SSM trainer guide in current main | Preserved as `docs/research/SSM_TRAINING_ENGINEERING_GUIDE_LIBRARY_RECOVERY_20261104.md` |
| Prior unified Cognitum branch `cognitum/specialists/ssm.py` | **Not in current main** | Restored bounded diagonal reference as `cognitum/research/ssm_recovered.py` |
| Historical K4 KAN trainable modules reported in Oct 26 provenance audit | Current main only has bounded portable inference | **Open**: verify original archive bytes and source/license before importing trainable code; `pykan-master` is *not* an exact substitute for user-owned `zogzoo_kan` |

## What has actually been evaluated

- Original archived HDC selftest was run locally using the materialized
  original `models.py/memory.py/core.py/text.py/parallel.py/metrics.py`
  and related files: **20 of 20 passed** on this Linux CPU session.
  The root package initializer was replaced locally by a minimal isolated
  initializer solely to run the archive without unrelated optional imports.
- Independent local HDC sanity checks of four model families at 256
  dimensions: BSC and MAP bind/unbind exact, FHRR near-exact, HRR
  noisy (as the method expects). Bank exact-item cleanup passed for all four.
  BSC/MAP SDM lookup and 3-factor exhaustive cleanup passed.
- Added CI tests in `tests/test_hdc_kan_ssm_recovery.py`: HDC family
  algebra, cleanup, sparse memory and factoring, existing portable KAN
  checkpoint inference and independent NumPy-versus-diagonal-SSM recurrence
  including chunk continuation.
- Added `tools/run_hdc_kan_ssm_recovery_benchmark.py` for **task-specific**,
  not cross-domain ranked, numerical/timing evaluation. C08's earlier
  exact/FTS5 baseline remains separate.
- Windows and Linux Python 3.11/3.13 CI must pass on the **latest** branch
  head before any restored component is accepted as cross-platform.

## Important limitations

The copied Library source may differ in trailing whitespace/newlines from
original file bytes; source-module identity must be confirmed by canonical
checksums before claiming byte-for-byte reproducibility. The recovered
user-owned Zog Zoo source is kept in an isolated research namespace;
`runner.py` is not registered as a production tool, and neither external
TorchHD nor pykan was vendored. Research training scripts and fixtures
must not inherit filesystem/network authority from Lu.

**Do not mistake restoration of modules for full HDC/KAN/SSM implementation.**
The K4 optimized overlay and historical KAN training files are still
distinct recovery gates. Trained selective SSM architectures remain future
implementation work. HDC ARM-low-power energy evaluation is deferred, with
the user's provisional hypothesis preserved.
