"""Synthetic-only protected NSIS candidate construction/reverification tests.

Never export these fixtures as an approved runtime or private release.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from argparse import Namespace

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts import cog_r3r1_protected_successor_candidate as b
from scripts import cog_r3r1_protected_successor_contract as c

SOURCE="104b84f8291ea3f22a3aac4e5ab1255dc0ce2c5f"
OWNER="DB9C7C9FCC675D8EE33D3F885007C136EE8BDB86"

def sha(x:bytes)->str:
    return hashlib.sha256(x).hexdigest()

def fixture(root:Path):
    stage=root/"staging"
    payload=stage/"payload"
    runtime=payload/"runtime"
    (runtime/"cognitum/mel").mkdir(parents=True)
    (stage/"Cognitum-SSM-R3R1-Protected.exe").write_bytes(b"UNSIGNED-TEST-CARRIER-NO-INSTALL")
    (payload/"cognitum-scm-production.exe").write_bytes(b"TEST-ONLY-NOT-PRODUCTION-SERVICE")
    (runtime/"python.exe").write_bytes(b"TEST-ONLY-PYTHON-NOT-EXECUTABLE")
    (runtime/"cognitum/mel/ssm_r5_production_child.py").write_bytes(b"# CI-only test frame\n")
    entries=[]
    for p in runtime.rglob("*"):
        if p.is_file():
            entries.append((p.relative_to(runtime).as_posix(),sha(p.read_bytes())))
    manifest=( "".join(f"{digest}\t{path}\n" for path,digest in sorted(entries))).encode("ascii")
    (runtime/"r3-r1-runtime.manifest").write_bytes(manifest)
    prov={"schema":"cognitum.ssm.r3r1.production_installer_runtime.v1",
          "runtime_manifest_sha256":sha(manifest),
          "external_manifest_approved_for_production":True,
          "original_production_source_sha":SOURCE,
          "python_sha256":sha((runtime/"python.exe").read_bytes()),
          "external_python_image_sha256":sha((runtime/"python.exe").read_bytes()),
          "runtime_file_count":len(entries),
          "actual_Core_grant":False,
          "external_output_release_authorized":False,
          "production_release_signer_approved":False,
          "independent_release_authority_approved":False,
          "test_fixture_not_real":True}
    (runtime/"r3-r1-runtime-provenance.json").write_text(json.dumps(prov)+"\n",encoding="ascii")
    args=Namespace(stage=stage,source_sha=SOURCE,owner_fingerprint=OWNER,
       runtime_manifest=sha(manifest),
       runtime_provenance=sha((runtime/"r3-r1-runtime-provenance.json").read_bytes()),
       cng_key_name="CognitumMachineR3R1V2",
       cng_public="2"*64,antirollback_public="3"*64,
       lu_issuer_public="4"*64,
       approved_candidate=None)
    return args,runtime

class CandidateSourceOnly(unittest.TestCase):
    def test_closed_candidate_byte_match_then_read_only_inspection(self):
        with TemporaryDirectory() as t:
            args,runtime=fixture(Path(t))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                b.candidate(args)
            self.assertEqual(json.loads(out.getvalue())["owner_gpg_signature_created"],False)
            record=(args.stage/"protected-successor.json").read_bytes()
            args.approved_candidate=sha(record)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                b.inspect(args)
            self.assertEqual(json.loads(out.getvalue())["status"],
                             "PASS_CANDIDATE_EXACT_STAGED_BYTES_RECHECKED_NOT_APPROVED")
            self.assertFalse((args.stage/"protected-successor.json.asc").exists())
            with self.assertRaises(ValueError):
                b.candidate(args)

    def test_tampered_child_refused_even_with_same_manifest(self):
        with TemporaryDirectory() as t:
            args,runtime=fixture(Path(t))
            with contextlib.redirect_stdout(io.StringIO()):
                b.candidate(args)
            args.approved_candidate=sha((args.stage/"protected-successor.json").read_bytes())
            child=runtime/"cognitum/mel/ssm_r5_production_child.py"
            child.write_bytes(child.read_bytes()+b"x")
            with self.assertRaises(ValueError):b.inspect(args)

    def test_replaced_nsis_refused_before_sign(self):
        with TemporaryDirectory() as t:
            args,runtime=fixture(Path(t))
            with contextlib.redirect_stdout(io.StringIO()):
                b.candidate(args)
            args.approved_candidate=sha((args.stage/"protected-successor.json").read_bytes())
            (args.stage/"Cognitum-SSM-R3R1-Protected.exe").write_bytes(b"DIFFERENT UNSIGNED TEST CARRIER")
            with self.assertRaises(ValueError):b.inspect(args)

    def test_wrong_source_sha_in_frozen_provenance_refused(self):
        with TemporaryDirectory() as t:
            args,runtime=fixture(Path(t))
            prov=runtime/"r3-r1-runtime-provenance.json"
            body=json.loads(prov.read_text())
            body["original_production_source_sha"]="a"*40
            prov.write_text(json.dumps(body)+"\n")
            args.runtime_provenance=sha(prov.read_bytes())
            with self.assertRaises(ValueError):
                b.candidate(args)

    def test_provenance_python_pin_or_approval_flags_refused(self):
        for key,value in (
            ("external_python_image_sha256","a"*64),
            ("runtime_file_count",0),
            ("actual_Core_grant",True),
            ("external_output_release_authorized",True),
            ("production_release_signer_approved",True),
        ):
            with self.subTest(key=key), TemporaryDirectory() as t:
                args,runtime=fixture(Path(t))
                prov=runtime/"r3-r1-runtime-provenance.json"
                body=json.loads(prov.read_text())
                body[key]=value
                prov.write_text(json.dumps(body)+"\n")
                args.runtime_provenance=sha(prov.read_bytes())
                with self.assertRaises(ValueError):
                    b.candidate(args)

    def test_added_runtime_file_refused(self):
        with TemporaryDirectory() as t:
            args,runtime=fixture(Path(t))
            (runtime/"rogue.py").write_bytes(b"fake")
            with self.assertRaises(ValueError):b.candidate(args)

if __name__=="__main__":
    unittest.main()
