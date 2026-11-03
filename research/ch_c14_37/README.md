# Cognitum CH-C14-37 — Three-UID verified proof-signing boundary (Linux)

**Research only; unchanged CH23–CH36 original mathematics; Windows deferred; Cognitum C14/G25 and Lu production unchanged.**

CH36 ran the mathematical proof worker **under the signing UID** in a separate process. CH37 removes that identity overlap. The original frozen CH23 15-case data remain authoritative and no synthetic optimizer cases are substituted.

## Security boundary

| Principal | Linux UID in disposable acceptance | May access | Must be denied |
|---|---:|---|---|
| Journal writer | 1000 | Own case-only signer socket | Either private key, sealed original source, verifier socket |
| Mathematical verifier | 1002 | Sealed original CH23 source and 224-bit MPFR; its **own verifier ticket key** | Signer's Ed25519 private key, signer socket |
| Witness signer | 65534 | Signer Ed25519 private key; immutable case/head/checkpoint pins; verifier **public** key; signed ledger | Verifier's source, verifier's private ticket key |

The verifier accepts only `case_id`, a 32-byte fresh signer challenge, and a protected policy digest over a Linux AF_UNIX socket. Group permissions *and* SO_PEERCRED restrict callers to the signer UID. The signer accepts only an original case ID from the writer, never a certificate, digest, verifier ticket, or signature from the writer.

For each accepted case, the verifier replays the 127-node CH33 checkpoint and six historical CH32 proof frames with the original 224-bit MPFR/CH29 binding checks, then signs a strict V1 ticket (case, nonce, policy, original source hashes, refusal status) with its own Ed25519 key. The signer checks that signature against an operator-pinned verifier public key/fingerprint, nonce, case, and independent original policy *before* creating a **V2 signer witness** that embeds the verifier-signed ticket. The signer performs no numerical verification and has no access to source material. Different key domains prevent inter-protocol signature substitution.

An external audit requires **both separately pinned public-key fingerprints and a pinned latest signed tip**. It verifies both signature layers, original CH32 journal heads, CH33 checkpoints (including raw checkpoint-file SHA-256), cases, generation links, distinct nonces, scientific refusal, and archive frame counts. A verified public signature alone cannot establish a trusted off-host anchor.

## Key invariants and failure semantics

1. Neither signer nor writer has a path or credentials allowing it to open the other account's private key. No private keys are included in release packages.
2. A forged, stale, malformed, repeated, cross-case, or cross-policy verifier ticket cannot become a signed CH37 witness. A duplicate original case is refused before and after independent proof work.
3. The signer serializes **only publication**; up to four proof workers can perform isolated MPFR verification under UID 1002. Concurrent same-case requests cannot publish twice.
4. Witness revisions are append-only, followed by atomic `HEAD` and protected `trusted_tip.json` publication with fsync. Any orphan revision, interrupted write, post-HEAD pre-tip failure, unpinned head, or unknown file requires explicit reconciliation. Neither verifier nor signer silently adopts a new pin.
5. CH37 does **not** grant global-optimality certification. The original CH29 gap threshold 0.05 remains unmet in all 15 cases. Scientific and production status: **NO-GO**.

## Tests

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q CH_C14_37/tests/test_protocol37.py

# Real account split, root-only disposable integration; uses the exact original package
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_37/harness37.py \
  --root /path/to/extracted/original_CH36_package --all \
  --result CH_C14_37/original15_results.json

# Independent public audit: fingerprints and signed tip must be supplied from a trusted external source
python CH_C14_37/audit37.py --original /path/to/extracted/original_CH36_package \
  --public CH_C14_37/CH37_public_witness \
  --signer-fingerprint '<externally-pinned-signer-sha256>' \
  --verifier-fingerprint '<externally-pinned-verifier-sha256>' \
  --tip '<externally-pinned-tip-sha256>'
```

The root-operated test harness uses `setpriv` and numeric UID 1000, 1002, 65534 and shared group 3101 in a **temporary** local directory, never a production identity; it cleans up private-key stores when complete. Source and proof copies are verifier-owned 0700, signer code and store signer-owned 0700. The verifier socket is 0660 in a verifier-owned setgid directory for the signer group; the signer socket is similarly protected for the writer group. Other UIDs are denied access by the kernel.

## Limitations

- A compromised verifier UID can forge its *own* verifier ticket; it **still cannot read the signer private key**. Signer compromise can issue unauthorized signer signatures. Remote/off-host trust and independent second witness do not yet exist.
- Python runtime and platform packages are not a kernel sandbox or formally verified implementation. A live production deployment needs its own service supervisor, secure provisioning and rotation, resource quotas, and privileged-deployment review.
- A root/kernel compromise bypasses UID boundaries. This work does not prove defense against malicious root, host kernel bugs, DMA, or adversaries with ptrace-equivalent privileges.
- The public auditor checks the mathematics **was attested by the verifier**; it does not itself rerun MPFR. The original 15-case acceptance run does rerun MPFR.
- No hardware power loss, durable independent off-host anchor, Windows/NTFS test, or production release is claimed.
