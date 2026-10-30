# Alpha P1: bounded native Protobuf process dispatch (Cognitum only)

Status: **tested standalone developer-reference**, never Lu CE enrollment, host authority, untrusted package confinement, production OS sandbox, or native Windows worker certification.

- `proto/cognitum/alpha_native.proto` is an additive Cognitum-only **binary Protobuf** envelope: version, request ID, operation, domain type URL, domain bytes; explicit success/failure status and epistemic flags in reply.
- `cognitum.alpha_native.run_once` receives a host-injected `HostAdmission`. Default admission is denied; the request wire contains **no grant** and request ID must match the admission. The class is constructible by any Python code, so **it is a test harness fence, not authenticated host security**.
- A closed allowlist currently admits only `calc.rational`; strict canonical Protobuf parsing rejects unknown fields, duplicates, wrong type URLs or unsupported versions. The regular bounded arithmetic parser is run before worker launch.
- The worker is a separate trusted subprocess with a fixed Python module and a 4-byte length-prefixed binary frame; no model-selected command, executable or filesystem path. The parent enforces timeout, maximum input/output, stderr/exit failure and recomputes the exact answer, rejecting forged success, wrong ID, mismatched result or claimed Lu/OS assurance.
- Worker timeout terminates the direct subprocess; this **does not** guarantee process-tree reaping, CPU/RAM confinement, secure environment isolation or real revocation-on-the-wire. Those remain C02/C04 and Windows gates.
- Research C08/C09 kernels do **not** enter this allowlist, registry or model-visible catalog. The existing standard registry is default-off.

Run: `python -m pytest -q tests/test_alpha_native.py tests/test_protobuf_codec.py` with Protobuf installed. This can execute on Linux or Windows. See `tools/smoke_alpha_native.py` for a deliberately authorized developer test call with non-authoritative output.

**Next acceptance:** pin packaging, test on actual Windows, add a host-owned token/lease and revocation fence, implement a supervisor with OS-enforced confinement and closeable descendant tree, and demonstrate Lu host-to-worker tool roundtrip separately under user permission. None are implied by the local smoke test.
