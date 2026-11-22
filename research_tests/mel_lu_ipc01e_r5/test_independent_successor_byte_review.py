"""Independent-source byte reviewer: positive observation and tamper refusal.

All fixtures are fake, never production. The review success bit does NOT
confer legal/owner approval, a signed release, Core grant or worker execution.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts import cog_r3r1_independent_byte_review as independent
from scripts import cog_r3r1_protected_successor_candidate as candidate
from research_tests.mel_lu_ipc01e_r5.test_protected_successor_candidate import fixture, SOURCE, OWNER

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def filled(root):
    args, runtime=fixture(root)
    extra=(
      "cognitum/mel/ssm_r5_fixed_child.py",
      "Lib/site-packages/numpy/__init__.py",
      "Lib/site-packages/scipy/__init__.py",
      "Lib/site-packages/google/protobuf/__init__.py",
      "Lib/site-packages/cryptography/__init__.py",
    )
    for rel in extra:
        path=runtime/rel
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text("# synthetic test stub: never a genuine production import\n")
    pairs=[]
    for path in runtime.rglob("*"):
        if path.is_file() and path.name not in (
            "r3-r1-runtime.manifest","r3-r1-runtime-provenance.json"):
            pairs.append((path.relative_to(runtime).as_posix(),
                          sha(path.read_bytes())))
    manifest=("".join(f"{dg}\t{rel}\n" for rel,dg in sorted(pairs))).encode("ascii")
    (runtime/"r3-r1-runtime.manifest").write_bytes(manifest)
    prov_file=runtime/"r3-r1-runtime-provenance.json"
    prov=json.loads(prov_file.read_text())
    prov["runtime_manifest_sha256"]=sha(manifest)
    prov["runtime_file_count"]=len(pairs)
    prov_file.write_text(json.dumps(prov)+"\n",encoding="ascii")
    args.runtime_manifest=sha(manifest)
    args.runtime_provenance=sha(prov_file.read_bytes())
    with contextlib.redirect_stdout(io.StringIO()):
        candidate.candidate(args)
    return args,runtime

class IndependentByteReview(unittest.TestCase):
    def test_full_fixture_observation_is_not_approval(self):
        with TemporaryDirectory() as td:
            args,_=filled(Path(td))
            sha_pin=sha((args.stage/"protected-successor.json").read_bytes())
            receipt=independent.review(args.stage,SOURCE,OWNER,sha_pin)
            self.assertEqual(receipt["status"],
                "PASS_INDEPENDENT_IMPLEMENTATION_BYTE_REVIEW_OBSERVATION_ONLY")
            self.assertFalse(receipt["independent_reviewer_approved"])
            self.assertFalse(receipt["original_owner_GPG_signature_verified"])
            self.assertFalse(receipt["read_only_source_checkout_verified"])
            self.assertFalse(receipt["output_or_ACK_authorized"])

    def test_mutated_library_refused(self):
        with TemporaryDirectory() as td:
            args,runtime=filled(Path(td))
            (runtime/"Lib/site-packages/scipy/__init__.py").write_text("tampered")
            with self.assertRaises(independent.ReviewRefused):
                independent.review(args.stage,SOURCE,OWNER)

    def test_altered_manifest_and_unlisted_file_refused(self):
        for kind in ("manifest","extra"):
            with self.subTest(kind=kind),TemporaryDirectory() as td:
                args,runtime=filled(Path(td))
                if kind=="manifest":
                    (runtime/"r3-r1-runtime.manifest").write_bytes(b"tamper")
                else:
                    (runtime/"added_entry.pyd").write_bytes(b"rogue")
                with self.assertRaises(independent.ReviewRefused):
                    independent.review(args.stage,SOURCE,OWNER)

    def test_wrong_reviewed_candidate_pin_refused(self):
        with TemporaryDirectory() as td:
            args,_=filled(Path(td))
            with self.assertRaises(independent.ReviewRefused):
                independent.review(args.stage,SOURCE,OWNER,"f"*64)

    def test_provenance_forged_core_grant_refused(self):
        with TemporaryDirectory() as td:
            args,runtime=filled(Path(td))
            prov=runtime/"r3-r1-runtime-provenance.json"
            content=json.loads(prov.read_text())
            content["actual_Core_grant"]=True
            prov.write_text(json.dumps(content)+"\n")
            with self.assertRaises(independent.ReviewRefused):
                independent.review(args.stage,SOURCE,OWNER)

    def test_reviewed_source_checkout_required_for_cli_path(self):
        with TemporaryDirectory() as td:
            args,_=filled(Path(td))
            fake=Path(td)/"untrusted-nongit-source"
            fake.mkdir()
            with self.assertRaises(independent.ReviewRefused):
                independent.review(args.stage,SOURCE,OWNER,None,fake)

if __name__=="__main__":
    unittest.main()
