# Cognitum C01–C19 library adoption audit — initial source-backed inventory

**2026-11-04.** The established-libraries-first decision is binding in
`docs/design/ADR-established-libraries-first-2026-11-04.md`.

This first pass inspected the repository's dependency manifest and representative
implemented source modules. **Library candidate ≠ validated installation.**
Remaining components without a source audit are explicitly marked pending.

| Components | Existing source evidence | Mature baseline / action | Audit state |
|---|---|---|---|
| C01–C04 | Native Protobuf, Python stdlib, cryptography optional; host-boundary and test fixtures | Keep native host authority and Protobuf; don't replace security with a scientific library | Preliminary |
| C05 | `scientific_math.py` uses Fraction, Decimal, mpmath; bounded custom polynomial/matrix reference | Evaluate SymPy, SciPy/NumPy, FLINT/Arb and HiGHS for any future non-reference capability; retain simple exact checks as independent oracle | Source inspected |
| C06–C07 | No full domain implementation confirmed by this inspection | SQLite/FTS, mature vector search and typed data stores as task requires | Pending domain inspection |
| C08 | `research/hdc_optional.py` has a custom 256-bit BSC binding reference | Evaluate user's TorchHD source/package before extending HDC operations | Source inspected; adoption pending |
| C09 | `research/kan_optional.py` / portable KAN uses NumPy and archived K4 | Compare supplied pykan and maintained packages; ensure checkpoint semantics and licenses | Source inspected; adoption pending |
| C10 | `formal_boolean.py` tiny exhaustive reference; `formal_smt.py` newly uses optional Z3/cvc5 | **Adopt Z3/cvc5 as SMT solvers**; own only schema, limits and independent validation | Implementation in PR #67; native CI pending |
| C11–C12 | Design coverage, domain implementation not audited | OR-Tools CP-SAT, SciPy HiGHS, CVXPY and appropriate graph/planning engines | Pending implementation |
| C13 | Design coverage, domain implementation not audited | SciPy.stats and established probability/Bayesian engines | Pending implementation |
| C14 | `causal_specialists.py` uses statsmodels, DoWhy, EconML, causal-learn, Tigramite optional | Preserve mature-library architecture and prior component closure | Source inspected, already closed |
| C15 | Existing external spatial/tracker work not audited in this pass | OpenCV, documented BoT-SORT/ByteTrack, geometry/tracker engines based on task | Pending source/fixture audit |
| C16 | `physics_motion.py` exact 1-D constant acceleration reference with Fraction | Keep analytic oracle; use SciPy integrators/established engines for general simulation | Source inspected |
| C17 | `temporal_filter.py` bounded scalar Kalman-like Decimal reference | Compare FilterPy, statsmodels, SSM libraries before generalized filter/sequence work | Source inspected |
| C18–C19 | Design coverage, domain implementation not audited | Evaluate PyTorch/learn2learn and established TDA packages (e.g. Ripser/GUDHI) based on required operation | Pending requirements |

Next implementation commits for each component must include a scoped library review
with confirmed supported Python/platform versions, current license obligations,
dependency lock/reproducibility, actual API execution, and baseline parity checks.
This initial matrix does **not** claim that all components have been thoroughly
verified, nor require installing every candidate library.

C10's next gate is true Z3/cvc5 runtime tests on Windows/Linux, exact typed wire
admission, status and proof-policy hardening. The old bounded-only C10 closeout
document is historical and **superseded** by the reopened development decision.
