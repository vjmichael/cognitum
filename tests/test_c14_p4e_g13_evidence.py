"""Tamper/omission tests for G13 evidence checker (separate from policy)."""
import copy
import json
import unittest
from cognitum import causal_integrated_assurance as integration
from tools import run_c14_p4e_g13_verify_report as report
from tools import run_c14_p4e_g13_acceptance as matrix

class G13EvidenceAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.good=json.loads(matrix.OUT.read_text())

    def test_complete_matrix(self):
        self.assertEqual(report.audit(self.good)['cases_checked'],32)

    def test_forged_external_grant(self):
        changed=copy.deepcopy(self.good)
        changed['results'][0]['external_action_allowed']=True
        with self.assertRaisesRegex(ValueError,'G13_FORGED_AUTHORITY_FLAG'):report.audit(changed)

    def test_forged_host_auth(self):
        changed=copy.deepcopy(self.good)
        changed['claims']['lu_host_authenticated']=True
        with self.assertRaisesRegex(ValueError,'G13_UNAUTHORIZED_RESEARCH_CLAIM'):report.audit(changed)

    def test_missing_case(self):
        changed=copy.deepcopy(self.good);changed['results'].pop()
        with self.assertRaisesRegex(ValueError,'G13_INVALID_DESIGN_OR_COUNT'):report.audit(changed)

    def test_duplicated_case(self):
        changed=copy.deepcopy(self.good);changed['results'][1]=changed['results'][0]
        with self.assertRaisesRegex(ValueError,'G13_DUPLICATE_CASE'):report.audit(changed)

    def test_false_allowlisted_disposition(self):
        changed=copy.deepcopy(self.good);changed['results'][0]['disposition']='INTEGRATION_ALLOW_ACTION'
        with self.assertRaisesRegex(ValueError,'G13_MATRIX_DISPOSITION_MISMATCH'):report.audit(changed)

    def test_changed_provenance_shape(self):
        changed=copy.deepcopy(self.good);changed['results'][0]['receipt_sha256']='invalid'
        with self.assertRaisesRegex(ValueError,'G13_MISSING_DIGEST'):report.audit(changed)

    def test_replay_spoof(self):
        changed=copy.deepcopy(self.good);changed['results'][-1]['replay_accepted']=True
        with self.assertRaisesRegex(ValueError,'G13_REPLAY_ACCEPTED'):report.audit(changed)

    def test_real_llm_claim_rejected(self):
        changed=copy.deepcopy(self.good);changed['claims']['real_llm_invoked']=True
        with self.assertRaisesRegex(ValueError,'G13_UNAUTHORIZED_RESEARCH_CLAIM'):report.audit(changed)

    def test_no_internal_authority_conflation(self):
        self.assertIn('NOT a signature',integration.__doc__)

if __name__=='__main__':unittest.main()
