# MEL-06A — genuine offline GGUF mathematical reference integration

**Status: partial local acceptance, not production or native Lu integration.** Exact remote source parent `e0b680acd9d5cfb1f42b6c83d7021a2190793c8d`; all 119 inherited MEL-05C manifest blobs match the reconstructed local checkout. The running 44558654551 acceptance branch was not modified. No additional CI workflow, branch, host permission, model registration, or production enablement is introduced.

## Implementation

- `cognitum/mel/model_reference.py`: trusted host scope and explicit allowlist, discovery from live admission grants, one bounded model request per reference turn, original reviewed JSON codecs, original Protobuf and Runtime worker path, approved KAN checkpoint only. The model never supplies a grant, review, checkpoint bytes, scope or receipt. Completed receipts are independently checked and replayed: MEL-05A VFA/HDC and MEL-05B KAN numerical verification. Feedback with non-within numerical verdict is withheld; no token, false success or fallback result is synthesized. The scalar threshold decision refers to the conservative displayed enclosure, not a rounded worker observation. The publication guard requires a separately supplied typed intent and compares closed final-answer JSON against the verified fact. No general natural-language intent parser or authenticated imported log is claimed.
- `tools/mel06a/schema_grammar.py`: bounded syntactic tool-choice alternatives derived from the live closed schemas, not a grant or semantic oracle. It constrains field shape but does not embed the target arguments or answer. Original codecs enforce bounds, dimensions, domains, units, and exact identity. Both basic JSON and schema-guided generation use the same greedy offline model. No retries in a trial; failed model outputs retained. Guarded VFA diagnostic is a distinct intervention after the original comparisons, not an amended score.
- `tools/mel06a/local_generate.cpp`: bounded CPU-only direct llama.cpp C API loader/generator, no server or external network. Qwen ChatML fixture prompt, maximum context 4096, output token limits, generic JSON or tool-shape grammar, greedy decoding; no real user data. Model file supplied by trusted operator. Archive must be checked against the known model identity before running. `experiment.py` retains raw prompts, completion text, receipt material, decisions and timing; `replay_evidence.py` independently reproduces mathematical results and final-answer gates from retained evidence (consistency only, not signed provenance).

## Actual evidence

Qwen2.5-1.5B-Instruct-Q4_K_M model SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`; uploaded three-part ZIP concatenated and CRC-tested. Pinned llama.cpp upstream source archive commit `7fe450e19305b828c199d602c23a8337aaa1f03b`, archive SHA-256 `8bffe21a3ecce942656e687eaa78276b8410653d740e8e6f1a3542b309706201`. C++ driver binary SHA-256 `da92a7e27a4bf3fe70242670ae80b1ea91b8aa5d27b50ad4395ebfeca78f0755`. CPU linked shared llama/ggml libraries built locally with GCC 14.2.0. The unnecessary server build was interrupted once the required libraries had compiled. Direct driver compiled and genuine offline inference succeeded.

46 scoped regression tests pass, zero failures, including all five admitted reference operations, route/scope/shape/grant refusal, no second call, wrong checkpoint, hash-consistent fabricated HDC/KAN/VFA results, exact output guard and conservative threshold display. An initial expanded test incorrectly supplied two KAN rows to the scalar answer gate; corrected the test fixture to one row without changing the gate. Prior 296 MEL-04B/05A/05B/05C regression results are historical; no claim that the full predecessor suite was rerun this turn. All 119 inherited source blobs verified.

| Cohort | Model-selected correct tool | Correct arguments | Actual admitted workers | Correct final answer |
|---|---:|---:|---:|---:|
| Basic JSON (3 tasks) | 3 | 1 | 1 | 1 |
| Schema-guided (same 3 tasks) | 3 | 2 | 3 | 2 |
| Guarded VFA follow-up (1 distinct trial) | 1 | 1 | 1 | 0 |

Unassisted: 1/3 correct on the matched diagnostic set. HDC alone returned [1,2,3], assisted [0,1] after exact distances [1,1,4]; KAN alone uncertain, verified interval around 1.5576015661428097 exceeded 1.5 and schema-guided answer above succeeded. Structured VFA initially used `dimensionless` rather than required token `1`, so semantic intent failed even though the mathematical worker executed. In the separate guarded trial exact arguments were generated without repair and the actual VFA worker returned observation 1.7649938051691907 with displayed enclosure [1.7649938051691907,1.764993805169191]. Inclusive threshold 1.764993805169191 is uncertain using that conservative display; the model returned `above` even when the computed decision `uncertain` was included. Publication rejected it. This is not evidence of improved uncertainty reasoning; it exposes the need for a stronger answer grounding mechanism. Four real negative model generations refused shell/fake result requests; additional deterministic adversarial tests attempted malicious payloads directly and verified zero admission or withheld payload. No scripted argument insertion or model-answer correction.

All five archived successful mathematical worker receipts were independently replayed, with the typed-intent publication gate accepting three of seven assisted attempts and refusing four. The replay is mathematical and transcript consistency, not cryptographic attestation that imported logs originated from the runtime. Small diagnostic sample, same model/settings, differing number of model calls and prompt lengths, no statistical or generalized reasoning claim. Timing covers each loaded-process inference including startup; not end-to-end production latency, energy or sustained throughput.

## Reproduce

From reconstructed source, with trusted local files and the pinned model hash verified:

```sh
cmake -S /path/to/llama.cpp-7fe450e19305b828c199d602c23a8337aaa1f03b -B /path/to/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TOOLS=ON -DLLAMA_CURL=OFF -DGGML_NATIVE=ON -DGGML_OPENMP=ON -DGGML_BLAS=OFF
cmake --build /path/to/build --target llama -j 4
g++ -O2 -std=c++17 -I/path/to/llama.cpp/include -I/path/to/llama.cpp/ggml/include tools/mel06a/local_generate.cpp -L/path/to/build/bin -Wl,-rpath,/path/to/build/bin -lllama -lggml -lggml-base -o /path/to/local_generate
python -m pytest -q research_tests/mel06a/test_reference.py
python -m tools.mel06a.experiment --driver /path/to/local_generate --model /path/to/qwen2.5-1.5b-instruct-q4_k_m.gguf --grammar /path/to/llama.cpp/grammars/json.gbnf --out /path/to/basic --threads 4
python -m tools.mel06a.experiment --driver /path/to/local_generate --model /path/to/qwen2.5-1.5b-instruct-q4_k_m.gguf --grammar /path/to/llama.cpp/grammars/json.gbnf --out /path/to/structured --threads 4 --structured
python -m tools.mel06a.experiment --driver /path/to/local_generate --model /path/to/qwen2.5-1.5b-instruct-q4_k_m.gguf --grammar /path/to/llama.cpp/grammars/json.gbnf --out /path/to/guarded --threads 4 --structured --guarded --case vfa-bound --no-negatives
python -m tools.mel06a.replay_evidence /path/to/basic /path/to/structured /path/to/guarded
```

Next: MEL-06A-R1, exact model-to-typed-intent and verified answer grounding, preserve refusal and expand held-out multi-model diagnostics (not post-hoc replace failures). Native Lu host integration and model promotion require separate authorization, exact-source and genuine installed acceptance. Do not alter current source branch while accepted cohort is running.
