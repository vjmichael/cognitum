# Cognitum C01–C19 mandatory reuse decisions — implementation queue

This is an adoption **decision queue**, not evidence that every candidate was installed, evaluated or licensed for shipping. Existing Cognitum/CH40 research is frozen as an independent baseline. Every candidate must pass its own reproducibility, platform, license, security, mathematical assurance, and end-to-end Lu+model evaluation gates.

| Cxx | First mature engine to evaluate | Custom code to preserve | Priority |
|---|---|---|---|
| C01 | Protobuf / standard validation | canonical typed result semantics | P3 |
| C02 | OS Job Objects, namespaces, cryptography | scoped broker and permissions | Safety gate |
| C03 | SciPy/statsmodels evaluation | independent provenance, trials | P2 |
| C04 | Lu-native registry and Protobuf | CE adapter, no parallel host | Safety gate |
| C05 | SymPy, NumPy, SciPy, FLINT | exactness/assurance class | P1 |
| C06 | SQLite FTS5, FAISS | Lu/ANSF canonical source authority | P2 |
| C07 | SQLite transactions | belief revision and version policy | P3 |
| C08 | torchhd / NumPy | task-specific HDC evidence | P2 |
| C09 | PyKAN/PyTorch | challenger+ablation policy | P2 |
| C10 | Z3, cvc5 | accepted proof policy | P1 |
| C11 | OR-Tools CP-SAT, HiGHS, SCIP | domain translation / checks | P1 |
| C12 | NetworkX, established planners | model-to-task translation | P3 |
| C13 | SciPy, statsmodels, PyMC, ArviZ | evidence, calibration policy | P1 |
| C14 | DoWhy, EconML, causal-learn, Tigramite; FLINT, IBEX, Ipopt, SCIP | identification boundaries + independent certification | ACTIVE |
| C15 | OpenCV, Open3D, ByteTrack/BoT-SORT/OC-SORT | persistent identities + custody | P2 |
| C16 | SciPy/SUNDIALS, established physics | invariants and resource-state custody | P2 |
| C17 | PyTorch and maintained SSM engines | adaptation gating | P2 |
| C18 | scikit-learn / PyTorch | permissions and retention constraints | P3 |
| C19 | GUDHI, Ripser, giotto-tda | end-task value proof | P2 |

Priorities are rough duplication-risk ordering, not release certifications. For every component: inspect existing code, freeze proper baseline, inspect dependency/third-party licenses, run a competent library comparison, then keep/replace/compose custom code based on measured gains and independent correctness.