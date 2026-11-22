# R3-R1: PRIVATE, OWNER-GPG SIGNED WINDOWS RELEASE

## Binding release policy

Cognitum's initial PERSONAL Windows release does NOT require a commercial or
self-signed Windows Authenticode certificate. The original Authenticode-only
path remains separate for any future public distribution; it is NOT required
by the private release. An unsigned Windows EXE can still show "Unknown
publisher" in Windows. GPG proves that the release bytes match a manifest
signed with the trusted owner key; it does NOT make Windows trust the publisher.

The user's GPG public key registered in GitHub Settings -> SSH and GPG keys
is not a private signing credential. Signing needs the corresponding private
key on a personally controlled GPG-capable Windows signer or a separately
authorized signing service. Never put private keys or passphrases in GitHub,
repository files, CI logs or this chat. Do not claim GitHub can sign with the
public key alone.

## Exact source and private GPG release

First use the already reviewed two-pass fresh frozen Python/NumPy/SciPy
production-runtime preparation procedure in
COG_R3R1_SIGNED_RELEASE_ADMISSION.md. It requires externally selected Git
source, original CPython SHA256 and a separately reviewed complete import
manifest SHA256. The last source pass emits the production runtime provenance
schema, but it does not sign or authorize mathematical output.

Then use scripts/cog-r5-physical02-r3-r1-private-gpg-build.ps1 on a
non-CI x64 Windows signing computer with the original PRIVATE GPG key
available to GnuPG, together with:
  - ExactSourceSha: exact checked-out 40-character original Git commit;
  - ApprovedRuntimeRoot: fresh approved production frozen runtime;
  - ApprovedRuntimeManifestSha256 and ApprovedRuntimeProvenanceSha256:
    externally reviewed and pinned full lower-case SHA256 values;
  - GpgPrimaryFingerprint: complete 40/64-character PRIMARY key fingerprint
    checked separately by the owner, not copied from untrusted artifacts;
  - TrustedPublicKeyFile: exported public GPG key file, NOT a private key;
  - GpgExecutable: absolute path to actual gpg.exe;
  - MakeNsisExecutable: absolute path to actual makensis.exe;
  - ProtectedStageRoot: precreated administrators-owned protected location.

The builder compiles only the separately scoped native no-worker SCM PE,
stages a fresh frozen runtime, compiles the NSIS installer, hashes the
installer and service, and writes private-release.json. It produces an ASCII
armored DETACHED GPG signature private-release.json.asc over the exact
original JSON bytes, and immediately re-verifies using the separately
supplied public key + exact owner fingerprint in an isolated GPG keyring.
The private key never leaves its owner. It refuses an existing release path,
dirty Git, CI, a test-only runtime, and altered original imports.

This is a complete *manifest signature* over the installer and service
binary digests, plus the frozen runtime and source pins; it is NOT an
embedded Authenticode signature in the Windows .exe files. Never describe
the executable's Windows signature state as Valid.

## Physical Windows installation (personal machine)

The operator must first review the release JSON, detached signature, source
SHA, and independent trusted GPG fingerprint. On the actual x64 Windows
computer, running as an explicitly authorized elevated administrator, use
scripts/cog-r5-physical02-r3-r1-private-gpg-physical.ps1 with:
  ReleaseRoot, TrustedPublicKeyFile, ExpectedPrimaryFingerprint,
  ExpectedSourceSha, GpgExecutable.

For example, invoke the PowerShell script with its named parameters and
the local absolute paths. Start with -WhatIf to review the intended SCM
mutation; that still performs the read-only GPG admission. The GPG verifier
checks cryptographic signature and all staged hashes *before* launching the
installer, and again before mutation. It refuses GitHub Actions, existing
installation/service state, invalid public-key identity, wrong source or
wrong release bytes. On successful installation, it verifies the original
installed SCM byte hash, SYSTEM/Administrators file ownership and ACLs,
the complete frozen-runtime import inventory, exact SCM service registration,
LocalSystem Session 0 process identity, restricted SID, and real stop/restart
with distinct process birth generations.

There is **no automatic uninstall on failure**. If the state is incomplete,
an independently authorized operator must inspect and recover it without
silently deleting or adopting another service.

## Acceptance boundaries

A successful private GPG sign/verify or private SCM installed lifecycle
receipt does not establish independent physical hardware custody, an
AppContainer numerical worker, production CNG receipt signer, authenticated
Lu Core PURE_COMPUTE grant, or output-release ACK. Those remain separately
blocked. The installed production SCM executable currently has NO worker.
This lane is for personal use; public trusted publisher signing may be
added later only if the user chooses it. Commercial Authenticode is not a
prerequisite to private Cognitum installed bootstrap acceptance.


## ECC owner key and staged local release driver (2026-11-21)

The owner selected the original Ed25519 primary GPG fingerprint
DB9C7C9FCC675D8EE33D3F885007C136EE8BDB86, key ID 5007C136EE8BDB86.
The owner demonstrated a local detached-signature "Good signature" and
verified the exported public key under Documents/cognitum-ecc-public.asc.
GitHub holds only the associated public key; the original signer key remains
in the owner's own Windows GnuPG installation. These observations do not
attest to a signed Cognitum binary.

Use native PowerShell 7 x64 from a checked-out exact reviewed Git source
tree. The script scripts/cog-r3r1-personal-release.ps1 provides five
explicitly separated phases, not a silent one-click approval:

1. Check: display actual Git source SHA and cleanliness, original python.exe
   SHA256, availability of Cargo/NSIS/GnuPG, local ECC secret-key listing and
   Documents public-key presence. Reports INFORMATION ONLY.
2. Candidate: after separate approval of the actual CPython image SHA256,
   build a NEW unapproved runtime output directory from original imports;
   record its full manifest hash for separate dependency/license review.
3. Production: with externally approved candidate manifest digest, rebuild
   from original source into ANOTHER NEW runtime directory. Record and
   separately approve its new provenance digest before signing.
4. Sign: with externally approved runtime manifest/provenance hashes, user
   public key, original ECC secret key and pre-created protected stage root,
   invoke the existing GPG/NSIS private-release builder. It compiles a
   NO-WORKER SCM bootstrap and detaches a GPG signature over private-release.json
   binding the actual package and runtime hashes.
5. Verify: independently repeat signature and original staged import checks
   in the existing isolated public-key verification path. READ ONLY.

Example diagnostic invocation from inside the exact checked-out repository:

    pwsh -NoProfile -File ./scripts/cog-r3r1-personal-release.ps1 -Phase Check

The diagnostic output is NOT approval. The actual exact Git revision and
Python image digest must be separately selected and accepted, not inferred
from the first candidate's self-report. All original host-side release
arguments (notably ApprovedManifestSha256 and ApprovedProvenanceSha256) must
come from their reviewed values.

After approval, equivalent invocations on the SAME reviewed Git source are:

    $sha = '<externally reviewed exact 40-character Git commit SHA>'
    $pyPin = '<approved lowercase SHA256 of selected python.exe>'
    $manifestPin = '<separately approved candidate runtime manifest SHA256>'
    $provPin = '<separately approved production runtime provenance SHA256>'
    $driver = './scripts/cog-r3r1-personal-release.ps1'
    pwsh -NoProfile -File $driver -Phase Candidate -ExactSourceSha $sha -ApprovedPythonSha256 $pyPin -RuntimeRoot 'C:\CognitumRelease\candidate-new'
    pwsh -NoProfile -File $driver -Phase Production -ExactSourceSha $sha -ApprovedPythonSha256 $pyPin -ApprovedManifestSha256 $manifestPin -RuntimeRoot 'C:\CognitumRelease\production-new'
    pwsh -NoProfile -File $driver -Phase Sign -ExactSourceSha $sha -ApprovedManifestSha256 $manifestPin -ApprovedProvenanceSha256 $provPin -RuntimeRoot 'C:\CognitumRelease\production-new' -StageRoot 'C:\CognitumProtectedStage'
    pwsh -NoProfile -File $driver -Phase Verify -ExactSourceSha $sha -ReleaseRoot 'C:\CognitumProtectedStage\r3r1-private-<first16sha>'

Each source/runtime directory must be fresh where required; the protected
signing stage must already exist and meet the existing SYSTEM/Administrators
ownership and no-untrusted-write ACL rules. Do not create fake approvals by
copying a computed SHA256 from the same execution without review. The Sign
phase does not install the package; actual installation still requires the
separately documented elevated -WhatIf/review and authorized physical
operation path. The GPG signature does not provide Windows Authenticode
publisher trust, grant Core PURE_COMPUTE, or authorize output/ACK. On CI,
all driver phases REFUSE, including Check, to avoid treating hosted state
as genuine original host evidence.


## Preflight dependency/key closure follow-up

The Check phase now reports python_runtime_inventory for the installed 64-bit
CPython prefix layout, importability and installed distribution versions of
NumPy, SciPy, Protobuf and cryptography. These observations are not a wheel-lock,
license review or independent production-source approval. Candidate/Production
refuse an unsuitable layout or missing imports; no network or pip mutation.
The Check phase also separately parses the exported GPG public key and reports
whether its ONLY primary fingerprint matches the selected primary ECC key.
Sign/Verify refuse a mismatched public identity before mutating/signing.
The NSIS discovery additionally checks both native Program Files paths for
a locally installed makensis.exe. On the owner's PC, run Check again after
NSIS installation; use the observed Python SHA256 only after review/approval.
