"""No self-approval of Cognitum R3-R1 private protected-successor candidate.

Pure metadata/independent-SHA contract tests. Owner-GPG signature verification,
physical installed machine/worker/signer and external antirollback are separate
native gates; these synthetic candidates authorize nothing.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts import cog_r3r1_protected_successor_contract as c

SOURCE="3ac8b241be555a1945f2255360d230a8a0c92a87"
OWNER_FP="DB9C7C9FCC675D8EE33D3F885007C136EE8BDB86"

def candidate():
    doc={field: "1"*64 for field in c.PIN_FIELDS}
    doc.update({field: False for field in c.REFUSAL_FIELDS})
    doc.update({
        "schema": c.SCHEMA,
        "role": "protected_ssm_production_successor_candidate",
        "source_sha": SOURCE,
        "approved_gpg_primary_fingerprint": OWNER_FP,
        "protected_service_name": c.REQUIRED_SUCCESSOR_SERVICE,
        "replaced_bootstrap_service_name": c.CURRENT_NO_WORKER_SERVICE,
        "preprovisioned_machine_cng_key_name": "CognitumMachineR3R1V2",
        "protected_runtime_file_count": 2413,
    })
    return doc

def audit(doc, **override):
    raw=c.canonical_candidate(doc)
    defaults=dict(
        externally_approved_manifest_sha256=hashlib.sha256(raw).hexdigest(),
        externally_approved_source_sha=SOURCE,
        externally_approved_gpg_primary_fingerprint=OWNER_FP,
    )
    defaults.update(override)
    return c.validate(raw, **defaults)

class ProtectedSuccessorContract(unittest.TestCase):
    def test_complete_closed_candidate_is_observation_only(self):
        found=audit(candidate())
        self.assertEqual(found["status"], "PASS_CLOSED_PROTECTED_SUCCESSOR_METADATA_PINS_OBSERVATION_ONLY")
        for flag in ("owner_gpg_signature_verified_by_this_function",
                     "independent_publisher_or_signer_approved",
                     "installed_worker_verified",
                     "external_antirollback_accepted",
                     "real_Lu_Core_grant_verified", "output_or_ACK_authorized"):
            self.assertIs(found[flag], False)

    def test_old_no_worker_release_cannot_be_protected_successor(self):
        d=candidate()
        d["source_sha"]=c.CURRENT_NO_WORKER_SOURCE
        with self.assertRaises(c.RefusedSuccessor): audit(d)

    def test_no_worker_or_ci_service_cannot_be_protected_successor(self):
        for service in (c.CURRENT_NO_WORKER_SERVICE, c.CI_QUALIFIER_SERVICE):
            with self.subTest(service=service):
                d=candidate()
                d["protected_service_name"]=service
                with self.assertRaises(c.RefusedSuccessor): audit(d)

    def test_owner_fingerprint_cannot_be_selected_from_signed_document(self):
        d=candidate()
        d["approved_gpg_primary_fingerprint"]="A"*40
        with self.assertRaises(c.RefusedSuccessor): audit(d)

    def test_wrong_manifest_pin_or_source_refused(self):
        d=candidate()
        with self.assertRaises(c.RefusedSuccessor):
            audit(d, externally_approved_manifest_sha256="a"*64)
        with self.assertRaises(c.RefusedSuccessor):
            audit(d, externally_approved_source_sha="a"*40)

    def test_claimed_installed_authority_never_sufficient(self):
        for key in sorted(c.REFUSAL_FIELDS):
            with self.subTest(key=key):
                d=candidate()
                d[key]=True
                with self.assertRaises(c.RefusedSuccessor): audit(d)

    def test_missing_zero_or_invalid_pins_refused(self):
        for field in sorted(c.PIN_FIELDS):
            with self.subTest(field=field):
                for value in ("0"*64, "f"*63, "G"*64):
                    d=candidate()
                    d[field]=value
                    with self.assertRaises(c.RefusedSuccessor): audit(d)

    def test_duplicate_extra_and_missing_manifest_fields_refused(self):
        d=candidate()
        d["unreviewed_absolute_executable_path"]="C:/Users/Public/evil.exe"
        with self.assertRaises(c.RefusedSuccessor): audit(d)
        d=candidate()
        del d["protected_ssm_child_sha256"]
        with self.assertRaises(c.RefusedSuccessor): audit(d)
        raw=c.canonical_candidate(candidate())
        corrupt=raw.replace(b'"role":', b'"role":"duplicate","role":')
        with self.assertRaises(c.RefusedSuccessor):
            c.validate(corrupt,
                       externally_approved_manifest_sha256=hashlib.sha256(corrupt).hexdigest(),
                       externally_approved_source_sha=SOURCE,
                       externally_approved_gpg_primary_fingerprint=OWNER_FP)

    def test_canonical_signed_manifest_is_not_arbitrary_json(self):
        d=candidate()
        raw=c.canonical_candidate(d)
        bad=raw[:-1]
        for attack in (bad, b" "+raw, raw.replace(b":", b": ", 1),
                       raw.replace(b"\n", b"\r\n")):
            with self.subTest(attack=attack[:12]):
                with self.assertRaises(c.RefusedSuccessor):
                    c.validate(attack,
                       externally_approved_manifest_sha256=hashlib.sha256(attack).hexdigest(),
                       externally_approved_source_sha=SOURCE,
                       externally_approved_gpg_primary_fingerprint=OWNER_FP)

    def test_ci_qualifier_cannot_mint_production_claim(self):
        d=candidate()
        d["preprovisioned_machine_cng_key_name"]="ci_key"
        with self.assertRaises(c.RefusedSuccessor): audit(d)
        d=candidate()
        d["protected_runtime_file_count"]=True
        with self.assertRaises(c.RefusedSuccessor): audit(d)
        d=candidate()
        d["protected_runtime_file_count"]=0
        with self.assertRaises(c.RefusedSuccessor): audit(d)

if __name__ == "__main__":
    unittest.main()
