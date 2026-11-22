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
