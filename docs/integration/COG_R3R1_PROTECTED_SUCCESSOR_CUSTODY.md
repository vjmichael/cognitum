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


## Candidate build, independent review, and owner-GPG signing

The protected-ssm-production Cargo feature builds a distinct native Windows
SCM executable with the fixed identity CognitumSsmProtectedV1. The compiler
explicitly rejects combining that feature with the CI-only protected SSM
qualification. No CI fixed-vector worker is shipped in this production build,
and no Lu Core operations are admitted yet.

The new cognitum-ssm-protected-successor.nsi carrier installs at the separate
Program Files\Cognitum\SSMProtected root, overrides /D relocation, refuses
existing protected installation or service, and pins read-only installed code.
It DOES NOT register or start the new service, create a persistent machine
CNG signer, provision the AppContainer, overwrite the owner's already accepted
no-worker service, or issue result/output authorization.

### Owner-release steps (only when reviewed inputs exist)

1. Review a NEW exact clean protected-successor Git commit and prepare a fresh
   full production frozen Python/NumPy/SciPy runtime with the original two-pass
   candidate/production workflow. The old 2,413-file no-worker frozen runtime
   cannot be renamed into a new production successor.
2. Independently approve the new runtime full-file manifest and provenance
   digests; separately obtain the public-key identity pins for the intended
   machine CNG signer, external antirollback authority and Lu Core issuer.
   These pins do not prove installation or enrollment. Missing identities
   cannot be invented or inferred from GitHub CI.
3. On the owner's personal x64 Windows build machine, run
   scripts/cog-r3r1-protected-successor-build-candidate.ps1 with all external
   pins. It builds the independent protected native service with Cargo locked
   offline, stages the exact frozen runtime and compiles the distinct NSIS.
   The Python manifest generator hashes the exact staged NSIS, service PE,
   Python executable, production SSM child and all frozen imports and writes
   the canonical protected-successor.json file exactly once. This is an
   UNAPPROVED byte candidate, not a signed production release.
4. A separate authorized reviewer checks original source, dependencies and
   license evidence, full frozen runtime closure, executable and installer
   byte identities, NSIS nonoverwrite behavior and external public identities.
   The reviewer supplies the approved SHA-256 of the EXACT canonical
   protected-successor.json by an independently trusted channel. Merely
   copying the builder's reported SHA is not independent approval.
5. Only THEN run scripts/cog-r3r1-protected-successor-sign.ps1 on the owner's
   actual personal signing host with the reviewed candidate manifest hash.
   It rechecks the complete staged bytes, uses the locally controlled owner
   ECC-GPG primary key for a detached protected-successor.json.asc, and
   verifies the signature in an isolated public-only GPG keyring. No private
   key or passphrase must enter GitHub Actions, the repo, or this chat.

The GitHub Windows/Linux workflow cog-r3r1-protected-successor-nsis.yml
qualifies only source structure, cargo feature separation, and a disposable
unsigned NSIS test install with a synthetic runtime. It cannot sign an
actual production release or supply an independent reviewer, CNG enrollment,
external monotonic authority, installed protected worker, or authentic Lu Core
operation grant.

Owner-GPG signing authenticates the source/byte manifest but does NOT grant
Windows Authenticode publisher trust, authenticate Lu operations or permit
output ACK. Real physical installation and persistent signer custody remain
separate explicit future acceptance gates. Until then output_or_ACK_authorized
must stay false.


## Separate full-byte pre-signing review

scripts/cog_r3r1_independent_byte_review.py is deliberately implemented
separately from the candidate emitter and its policy module. It recomputes
each of the staged frozen Python, NumPy, SciPy, cryptography, Protobuf and
Cognitum files, their runtime manifest and provenance, native SCM image,
and NSIS SHA-256. It separately checks the new source SHA and existing
owner-GPG primary fingerprint and refuses a reused no-worker release.
The CLI additionally requires a clean Git checkout at that exact source
SHA on the reviewing machine, and can compare an independently supplied
candidate manifest digest using --expected-candidate-sha256.

This independent IMPLEMENTATION is not itself an independent HUMAN review
or a license-approval record. Its output always retains
independent_reviewer_approved=false and
original_owner_GPG_signature_verified=false. In particular it does NOT
extract every embedded file from the NSIS installer and compare them with
the staged runtime on an independently administered Windows machine;
that separate package install-and-compare review remains mandatory before
external approval and owner signing.

The reviewing party should run this read-only reviewer on the exact fresh
candidate after the owner has prepared the full frozen production runtime.
An approval must identify the exact source SHA, reviewed candidate manifest
SHA-256, frozen runtime and NSIS bytes, the independent reviewer's authority
and dependency/license decisions. It must originate outside the candidate
generator and must not be inferred from this tool's PASS status.

A local owner ECC-GPG signature is NOT available in this chat: the signing
script requires the existing private key on the physical owner Windows host.
No CI-only key or user secret may be substituted. The personal signing
step may only run after independent approval, and the detached signature
must be reverified before any physical installation.
