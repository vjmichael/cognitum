# Cognitum CH-C14-38 — Four-UID, key-isolated mathematical attestation

**Linux research only. Windows deferred. No changes to production Cognitum C14/G25 or Lu. Scientific global certification remains NO-GO.**

## Objective and assurance boundary

CH37 kept the verifier's mathematical execution and its Ed25519 attestation key in UID 1002. CH38 places the attestation signing key in an entirely different Linux UID, 1003, while keeping the final independent witness signer in UID 65534 and the untrusted journal writer in UID 1000.

| Principal | Disposable Linux UID | Trusted material and permitted action |
| --- | ---: | --- |
| Requesting journal writer | 1000 | May request only a frozen original case through witness socket |
| Mathematical verifier | 1002 | Owns immutable CH23/CH33 originals, proof replay workers; **no private signing keys** |
| Verification attestor | 1003 | Owns *attestor* Ed25519 key, frozen case policy; accepts only signer UID and contacts math UID |
| Final witness signer | 65534 | Owns *independent final* Ed25519 key, pinned attestor public key, frozen policy and durable ledger |

The writer-to-signer, signer-to-attestor and attestor-to-math AF_UNIX IPC paths are restricted with **both directory/socket permissions and SO_PEERCRED**. Signer and attestor each refuse requests from other UIDs. The signer cannot connect directly to the mathematical process. The mathematical process cannot open either private signing key. The attestor cannot open mathematical proof files or the final signing key.

CH38 uses new, domain-separated Ed25519 ticket/witness signatures. The attestor requires a one-use nonce, exact frozen case and policy, and a structurally valid mathematical result with pinned original CH32 head and CH33 checkpoint. Only then does it issue a signature. The final signer separately verifies that signature and challenge before serial durable publication; external audit validates the two signatures and all 15 frozen pins against original evidence.

**Crucial limit:** UID 1003 cannot independently establish mathematical truth from a JSON result. A compromised mathematical verifier UID 1002 could submit a fabricated *in-scope* success report, and the attestor would sign it despite key isolation. This milestone proves key and process isolation and actual original-data replay in the measured acceptance run, **not Byzantine mathematical-verifier correctness**. A following milestone should add independent proof checking outside the compromised-verifier trust boundary, and an off-host/append-only anchor.

## Reproduction

Extract the complete CH38 ZIP, which retains all CH37 original files and adds `CH_C14_38`:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q CH_C14_38/tests/
# Real OS UIDs, root-only, unchanged original CH23 frozen cases:
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_38/harness38.py --root /path/to/extracted/base --all --result CH_C14_38/original15_results.json
# Public audit requires independently pinned signing key fingerprint, attestor fingerprint, and latest tip:
python CH_C14_38/audit38.py --original /path/to/extracted/base --public CH_C14_38/CH38_public_witness \
 --signer-fingerprint '<external signer fingerprint>' --attestor-fingerprint '<external attestor fingerprint>' \
 --tip '<external latest signed tip>'
```

No private keys are packaged. Original frozen CH23–CH37 sources, checkpoints and evidence must remain unchanged. The public auditor **does not** replay MPFR by itself. Test execution on the original data does.

## Storage/recovery scope

CH38 inherits fail-closed CH37 signer V2 publication ordering: fsynced revision, atomic HEAD, fsynced trusted tip, strict orphan detection and explicit reconciliation. Dedicated real-kernel ENOSPC tests were completed in CH36. They are not reclassified as new CH38 fault coverage. No off-host authority, power-cut guarantee, genuine EDQUOT kernel test or Windows testing is claimed.
