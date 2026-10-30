"""DoWhy uploaded-main source validation; never a certified 0.14 worker gate."""
import hashlib
import os
from pathlib import Path
import sys
import unittest

from cognitum import causal_dowhy_backend as production
from cognitum.proto import causal_dowhy_pb2 as d
from tests.test_c14_dowhy_adapter import make_request
from tools.run_c14_p4e_g6_crosslibrary import (
    compare,verify_development_receipt,SOURCE_VERSION,SOURCE_BACKEND,SOURCE_ASSURANCE,
)


class UploadedMainDoWhyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = os.environ.get('COGNITUM_DOWHY_SOURCE')
        cls.venv = os.environ.get('COGNITUM_DOWHY_PYTHON',sys.executable)
        if cls.source:
            cls.sample=compare(cls.source,cls.venv,refutation=True,include_econml=False)
            # Read serialized child output directly for replay tampering tests.
            import subprocess
            from tools.run_c14_p4e_g6_crosslibrary import __file__ as harness
            cls.request=make_request(homogenous=True,refutation=True).SerializeToString(deterministic=True)
            proc=subprocess.run([cls.venv,'-I',str(Path(harness).resolve()),'--child','--source-root',str(Path(cls.source).resolve())],
                                input=cls.request,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=True)
            cls.reply=proc.stdout

    def require_source(self):
        if not self.source:
            self.skipTest('Uploaded DoWhy source explicitly absent; positive runtime not certified')

    def test_uploaded_version_not_release_proven(self):
        self.require_source()
        self.assertEqual(self.sample['source_version_declared'],SOURCE_VERSION)
        self.assertFalse(self.sample['source_zip_version_certified'])
        self.assertFalse(self.sample['production_v014_receipt_verified'])

    def test_real_dowhy_estimation_and_dev_receipt(self):
        self.require_source()
        self.assertTrue(self.sample['dowhy_dev_receipt_verified'])
        self.assertAlmostEqual(self.sample['dowhy_ate'],0.5,places=8)
        self.assertTrue(verify_development_receipt(self.request,self.reply))

    def test_placebo_is_only_a_diagnostic(self):
        self.require_source()
        parsed=d.DoWhyResult.FromString(self.reply)
        self.assertTrue(parsed.refutation_executed)
        self.assertEqual(parsed.refutation_reason_code,'PLACEBO_DIAGNOSTIC_ONLY')
        self.assertEqual(parsed.assurance,SOURCE_ASSURANCE)
        self.assertFalse(self.sample['model_assumptions_empirically_proven'])

    def test_production_receipt_rejects_development_source(self):
        self.require_source()
        self.assertEqual(d.DoWhyResult.FromString(self.reply).backend_id,SOURCE_BACKEND)
        self.assertFalse(production.verify_dowhy_receipt(self.request,self.reply).numeric_verified)

    def test_forged_effect_rejected(self):
        self.require_source()
        tampered=d.DoWhyResult.FromString(self.reply)
        tampered.estimated_ate='1000'
        self.assertFalse(verify_development_receipt(self.request,tampered.SerializeToString(deterministic=True)))

    def test_forged_authority_rejected(self):
        self.require_source()
        tampered=d.DoWhyResult.FromString(self.reply)
        tampered.assurance='CAUSAL_GRAPH_PROVEN'
        self.assertFalse(verify_development_receipt(self.request,tampered.SerializeToString(deterministic=True)))

    def test_cross_request_replay_rejected(self):
        self.require_source()
        other=make_request(homogenous=True,refutation=True)
        other.estimation.observations[0].count += 1
        self.assertFalse(verify_development_receipt(other.SerializeToString(deterministic=True),self.reply))

    def test_forged_refutation_rejected(self):
        self.require_source()
        tampered=d.DoWhyResult.FromString(self.reply)
        tampered.refutation_reason_code='PROVEN_CAUSATION'
        self.assertFalse(verify_development_receipt(self.request,tampered.SerializeToString(deterministic=True)))

    def test_exact_reference_has_no_causal_truth_claim(self):
        from cognitum import causal_dowhy_backend as b
        r=make_request(homogenous=True)
        raw=r.SerializeToString(deterministic=True)
        _,model,total,buckets=b._parse(raw)
        self.assertEqual(b._preflight(r,model,total,buckets),__import__('fractions').Fraction(1,2))
        r.estimation.identification.adjustment.clear()
        with self.assertRaises(ValueError):
            b._preflight(r,model,total,buckets)

    def test_cross_library_comparison_when_econml_available(self):
        self.require_source()
        try:
            from importlib.metadata import version
            if version('econml')!='0.17.0':
                self.skipTest('real EconML 0.17.0 absent')
        except Exception:
            self.skipTest('real EconML 0.17.0 absent')
        paired=compare(self.source,self.venv,refutation=False,include_econml=True)
        self.assertEqual(paired['reference_exact_ate'],'1/2')
        self.assertLess(paired['dowhy_econml_absolute_difference'],.08)
        self.assertFalse(paired['methods_equal_by_construction'])


if __name__=='__main__':unittest.main()
