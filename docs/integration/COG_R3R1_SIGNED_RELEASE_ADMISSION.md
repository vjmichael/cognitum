# R3-R1 production release: separate publisher and approval custody

STATUS: source-only readiness; NOT an independently signed release, NOT a
physical Windows acceptance and NOT Lu Core/SSM output authorization.

The previous acceptance qualified only an UNSIGNED Windows NSIS package, its
protected Program Files payload, and its no-worker installed SCM lifecycle.

## Fresh production runtime source (not a promoted CI fixture)

Before signing, an independently reviewed original Windows x64 Python +
NumPy/SciPy/Protobuf/cryptography source installation must be selected.
The existing fixture-only preparer emits the test schema and is NOT a
production package. Its accepted CI artifacts cannot be renamed or copied
into a production release.

A two-pass source builder now uses the same reviewed import-closure algorithm
but creates **fresh separate** output directories on a non-CI native Windows
host. It requires an exact original clean Git SHA and independently pinned
Python executable SHA256 in BOTH passes:

```powershell
python scripts/cog_r5_r3_r1_bundle.py prepare-candidate --root C:\CognitumRelease\candidate-<unique> --repo C:\reviewed\cognitum --source-sha <40-char-original-git-SHA> --approved-python-sha256 <64-char-approved-python-SHA256>
```

The candidate has schema
`cognitum.ssm.r3r1.unapproved_production_candidate.v1`, reports the full
runtime manifest digest, and explicitly denies publisher, Core and output
release authority. A separately authorized reviewer must inspect all
candidate import bytes, source dependency licenses, numerical behavior and
the complete manifest SHA256 and approve the exact original closure. The
first-pass candidate itself must NOT be signed or installed.

The second pass builds **again from original Git/Python inputs**, not the
candidate directory, and requires the prior independently approved digest:

```powershell
python scripts/cog_r5_r3_r1_bundle.py prepare-production --root C:\CognitumRelease\approved-runtime-<unique> --repo C:\reviewed\cognitum --source-sha <same-original-SHA> --approved-python-sha256 <same-approved-python-SHA256> --approved-manifest-sha256 <independently-approved-manifest-SHA256>
```

This pass refuses an altered original import closure, a modified original
Git checkout, a mismatched CPython image, a CI host, or a reused output
directory. Only its **fresh** runtime receives
`cognitum.ssm.r3r1.production_installer_runtime.v1` provenance. Its
manifest/provenance hashes must then be independently recorded and approved
for the signing script. It cannot create a signing key, legal approval,
original Lu grant or signed release itself.

## Controlled release procedure

1. An independent release authority selects and approves the exact Cognitum
   commit SHA, original frozen Python/NumPy/SciPy dependencies, production
   runtime manifest and provenance hashes, and the publisher identity.
2. A real Windows signing host holds the existing code-signing certificate
   and private key (never upload it to GitHub or ChatGPT). On the approved
   SHA it executes cog-r5-physical02-r3-r1-build-signed-release.ps1 with
   the exact source and frozen-runtime SHA256 pins, real NSIS/SignTool and
   a protected administrators-owned staging directory. The builder signs
   the separate production SCM PE and outer NSIS EXE and issues a candidate
   receipt whose output and physical acceptance booleans are FALSE.
3. A DIFFERENT independent release approver checks those bytes, source,
   publisher certificate, signer/installer/SCM digests, and frozen runtime.
   It creates an exact UTF-8 JSON with precisely these keys:
      schema = cognitum.ssm.r3r1.independent_release_approval.v1
      exact_source_sha = externally approved 40-char lower-case commit
      signed_installer_sha256 = approved complete signed NSIS SHA256
      signed_service_sha256 = approved signed production SCM PE SHA256
      runtime_manifest_sha256 = independently approved manifest SHA256
      runtime_provenance_sha256 = independently approved provenance SHA256
      publisher_certificate_sha256 = raw publisher X509 certificate SHA256
      permits_Core_grant = false
      permits_output_release = false
   It uses its OWN existing certificate/private key to produce a SHA256
   detached CMS/PKCS#7 P7S signature over the exact JSON file bytes, with
   exactly one signer. The approved release-authority certificate's RAW
   X509 SHA256 MUST come from a separate trusted channel and MUST differ
   from the publisher certificate. A detached signature does not by itself
   establish legal organizational approval.
4. On the physical target Windows computer, use the read-only
   cog-r5-physical02-r3-r1-admit-signed-release.ps1 with the protected
   release directory, exact source SHA, JSON, P7S, and both externally
   pinned certificate SHA256s. It verifies the detached signature and
   exact approved source/installer/executable/runtime byte identities,
   existing publisher Authenticode and protected staging. It never runs
   an installer or grants Core operations.
5. After explicit elevated 64-bit Windows operator approval, run
   cog-r5-physical02-r3-r1-deploy-approved-release.ps1 with the SAME
   arguments. It repeats admission before mutation, refuses existing
   trees/services or GitHub Actions, invokes the genuine signed installer,
   checks and enrolls the signed no-worker SCM host, and independently
   qualifies stop/restart and protected runtime. On any error, leave the
   incomplete protected installation for independently authorized review.
   Never silently adopt, overwrite or delete another installed service.

## Bounded evidence

A passing detached CMS check establishes only signature integrity and
exact certificate pin. A passing staged release admission establishes
only observed original approved signed release-byte identity. A passing
physical deployment script is only a signed no-worker SCM lifecycle
observation, not independent hardware attestation and not full production
acceptance. Actual nonadministrator AppContainer mathematical execution,
production CNG terminal receipt signer and original Lu Core PURE_COMPUTE
operation grant require separate installed evidence. The production
bootstrap continues to reject all operations and output acknowledgments.

The repo currently contains NO independent publisher signing key, no signed
release package or independent approval certificate, and no physical
installed receipt. No production release should be claimed from CI.
