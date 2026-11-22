# R3-R1 protected SSM successor: private GPG and installed custody

## Binding scope

The owner-accepted ECC-GPG-signed NSIS **NO-WORKER** bootstrap remains
installed under `CognitumSsmSupervisorV1`. Its original production bytes
were accepted on the owner's Windows computer. It MUST NOT be silently
overwritten, recast as the protected mathematical service, reinstalled or
uninstalled to satisfy a new CI gate. The disposable test-only service
`CognitumSsmProductionQualifierV1` is also NOT an installed release.

A future explicitly authorized protected mathematical release must instead
use the **distinct** Windows SCM identity `CognitumSsmProtectedV1` and
a freshly built, independently pinned native image and complete frozen
runtime. A Windows physical administrator and owner must explicitly approve
a new installation transaction. A passing source test does not approve that
transaction.

For the owner's personal release, **ECC GPG is the required package manifest
signature**. Windows Authenticode is optional and is not a blocker. A valid
GPG signature proves integrity and the signing key's identity, not Windows
publisher trust, independent approval, licensed software status or Lu Core
authorization.

## Implemented read-only gates

1. `scripts/cog_r3r1_protected_successor_contract.py` defines a CLOSED
   canonical ASCII JSON + LF successor manifest. It rejects unknown or
   duplicate fields, noncanonical bytes, all-zero/wrong SHA pins, the
   previously accepted no-worker source, either earlier service name and
   any true claim of physical installation, protected signer acceptance,
   antirollback freshness, authentic Core grant or output permission.
2. The approved successor manifest is `protected-successor.json`. The
   exact manifest SHA-256, full source SHA and owner-GPG primary fingerprint
   must arrive independently from the signed manifest. The detached owner
   signature is `protected-successor.json.asc`. No signing keys, passphrases
   or private material are accepted by the verifier.
3. `scripts/cog-r3r1-protected-successor-custody.ps1` is a read-only
   **physical Windows** observation. It requires those independent pins,
   verifies the original detached owner-GPG signature inside a disposable
   isolated keyring, checks exact protected NSIS + installed native
   supervisor + frozen Python/child SHA-256, invokes the original complete
   runtime manifest/ACL verifier, checks the **distinct** running LocalSystem
   Session-0 SCM service, then calls the already-reviewed native
   `cog-r3r1-production-cng-observe.ps1` to open an **existing**, independently
   pinned, nonexportable LocalMachine ECDSA-P256 signer. It creates no key,
   service, grant, mathematical job, or output, and never silently adopts
   the accepted no-worker image.
4. A PASS from the read-only gate remains
   `PASS_DISTINCT_GPG_PINNED_PROTECTED_SCM_RUNTIME_CNG_OBSERVATION_ONLY`.
   It does **not** verify that an actual AppContainer worker was launched
   by that installed service, that it completed an authenticated operation,
   that an external authority committed the operation's monotonic
   antirollback state or that production terminal receipts were signed.

## Independent admission before a physical successor install

An authorized operator and separate source/byte reviewer must first select:

- A new exact full protected-successor Git source SHA, not the original
  frozen no-worker source or a disposable CI build.
- Complete original native successor binary, protected NSIS package,
  frozen Python/NumPy/SciPy runtime manifest + provenance and production
  child source SHA-256 pins.
- The installed OS identity, ACL and service recovery plan for a persistent
  low-privilege local user and **no-capability** AppContainer profile.
- The existing LocalMachine CNG signer name and SHA-256 of its public
  ECCPUBLICBLOB, approved externally without creating or exporting a key.
- The **independent external antirollback authority** key identity and
  original Lu Core issuer public identity. Those pins alone do NOT prove
  a fresh antirollback check or authentic per-operation authorization.

The manifest must keep all acceptance and release claims false. Use the
contract validator to check candidate structure before the owner produces
a detached signature over the EXACT canonical bytes. The owner GPG private
key must stay under the owner's control. Do not move it into a GitHub Actions
workflow for physical release signing.

A new protected installer and physical service upgrade do **not** exist
as accepted artifacts yet. The signer observer cannot provision the
persistent production key; a real authorized machine administrator and
independent reviewer must do that. The read-only installed gate can only
pass **after** the separately approved successor is actually installed;
it is NOT an installer.

## Recovery and authorization still open

The present SCM CI qualification already proves prelaunch create-once+
sync, a fixed SSM calculation inside a genuine Windows AppContainer/Job,
CNG-signed terminal binding, actual second SCM start replay refusal and
an independent uncertain/partial-terminal decision matrix. This is
**source-level CI-only**. An attacker capable of deleting or rolling back
the local journal is not excluded by a signed local file. Never auto-clear
a missing prelaunch marker, replay an uncertain operation, or infer a
fresh external monotonic checkpoint from the same host's state.

Production successor acceptance requires actual physical Windows
installation and post-restart Job-empty/cancellation/replay testing, and
an independently maintained/queried external antirollback authority.
A separately authenticated Lu Core PURE_COMPUTE operation grant must be
verified at the actual operation boundary. Until then:
`output_or_ACK_authorized=false`, no grant consumption, no
mathematical result delivery or ACK, no production claim.

This work deliberately contains **no auto-upgrade or new owner command**
to operate on the accepted installed service.
