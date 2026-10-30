# C14 P4E G4 — Uploaded Source Admission and Dependency Closure (2026-10-28)

## Purpose and boundary

This checkpoint accepts user-provided source snapshots for the optional mature C14 backends and introduces a reproducible **offline source-admission preflight**. No external vendor source is bundled. No new model-accessible tool, Protobuf operation, host permission or native Windows security capability is enabled. P4E G3's genuine Tigramite PCMCI/PCMCI+ evaluation is preserved unchanged.

The prior `dowhy-main.zip` and the user-supplied replacement `dowhy-main (1).zip` have the **same SHA-256 digest**:
`fc7ed28888bcb8f95a8a00ff752c01269b21ab5a442bbfe264c4c8608381c97c`.
The replacement was selected for this development checkpoint. Both original uploaded files remain untouched.

## Source identity findings

| Package | Supplied source | SHA-256 | Version evidence | Runtime result |
|---|---|---|---|---|
| DoWhy | `dowhy-main (1).zip` | `fc7ed28888bcb8f95a8a00ff752c01269b21ab5a442bbfe264c4c8608381c97c` | `__version__ = 0.0.0`, Poetry dynamic VCS version; **not proof of v0.14** | Source import blocked; causal-learn absent |
| EconML | `EconML-main.zip` | `c034b1e108a106d0d88d1e544b2fc3263312a50717e9e91ddb22a9e13220eac3` | Source `_version.py` declares **0.17.0**; no git tag attestation | Source import blocked; `sparse` absent |
| causal-learn | `causal-learn-main.zip` | `76627ec52c6786e6307bea10cea14b93ebe5213dc34fdff740f9c61bf3826de6` | Source `setup.py` declares **0.1.4.8**; no git tag attestation | Source import blocked; `momentchi2` absent |

The DoWhy ZIP contains a GitHub symlink at `docs/source/docs/images`. The new preflight records this as **not safe for unfiltered extraction**. A metadata-only inspection does not follow or materialize the symlink.

## Requested next dependency packages

- **momentchi2 0.1.8:** universal Python wheel (`momentchi2-0.1.8-py3-none-any.whl`), for causal-learn. Pin package SHA-256 in the offline wheelhouse before executing.
- **sparse** (PyData sparse): select a compatible version and wheel based on the verified EconML 0.17.0 dependency range and Python 3.13 constraints; pin SHA-256. Source: https://pypi.org/project/sparse/.
- **DoWhy v0.14 tagged source**, ideally the GitHub release source archive or a distribution with trusted version metadata. A second `main` ZIP does not establish the release tag.
- Further transitive dependencies may emerge only after these are supplied. No package installation is marked complete.

## Executed tests

- `PYTHONPATH=. python -m unittest tests.test_c14_vendor_preflight -q`: **13 passed**.
- `PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c14*.py' -q`: **388 run, 17 skipped, zero failed**, i.e. 371 passed. G3 baseline retained. Counts include new 13 tests.
- `PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c13*.py' -q`: **141 run, two skipped, zero failed**, i.e. 139 passed.
- `PYTHONPATH=. python tools/verify_protobuf_schemas.py`: **41/41 independent schema/binding matches**.
- Separate source-import probes run under Python `-I` from explicit local archive extract locations. Each failed due to the missing dependency above. This is **not genuine DoWhy/EconML/causal-learn scientific execution**.
- Prior genuine Tigramite runtime results were not rerun in this gate.

## New files and evidence

- `tools/inspect_c14_vendor_archives.py`: read-only source archive metadata inspection, checks duplicates/traversal/link handling, declared-version evidence, and local dependency inventory.
- `tools/probe_c14_uploaded_source_imports.py`: bounded isolated-python source-import probes and explicit runtime-nonclaim.
- `tests/test_c14_vendor_preflight.py`: 13 positive/negative tests, including real archive inspection.
- `P4E-G4-source-dependency-evidence.json`, `P4E-G4-source-import-probe.json`: generated local evidence without bundling uploaded third-party source.

## Open gates

Pinned DoWhy v0.14 scientific execution; real EconML 0.17.0 and causal-learn 0.1.4.8 scientific execution; complete offline dependency closure/license review; native Windows Job Object/AppContainer containment; authenticated Lu host admission; reproducible causal-method performance campaigns and model A/B testing. **Never treat archive inspection, API import, or synthetic boundary tests as a passing scientific or security integration gate.**
