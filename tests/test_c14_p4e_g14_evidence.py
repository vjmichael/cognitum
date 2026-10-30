import copy
import json
import unittest
from tools.run_c14_p4e_g14_audit import audit,REPORT

class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.good=json.loads(REPORT.read_text())
    def test_evidence_shape(self):self.assertEqual(audit(self.good)['audited_cases'],2)
    def test_forged_lu_authentication(self):
        d=copy.deepcopy(self.good);d['actual_lu_host_authenticated']=True
        with self.assertRaisesRegex(ValueError,'OVERCLAIMED'):audit(d)
    def test_forged_llm(self):
        d=copy.deepcopy(self.good);d['real_llm_invoked']=True
        with self.assertRaisesRegex(ValueError,'OVERCLAIMED'):audit(d)
    def test_fake_worker_origin(self):
        d=copy.deepcopy(self.good);d['cases'][0]['worker_origin_authenticated']=True
        with self.assertRaisesRegex(ValueError,'INVALID_WORKER_REPORT'):audit(d)
    def test_wrong_backend_pinning(self):
        d=copy.deepcopy(self.good);d['cases'][1]['version']='99.9'
        with self.assertRaisesRegex(ValueError,'INVALID_WORKER_REPORT'):audit(d)
    def test_action_grant_claim(self):
        d=copy.deepcopy(self.good);d['external_actions_authorized']=1
        with self.assertRaisesRegex(ValueError,'OVERCLAIMED'):audit(d)
    def test_swapped_backend_data(self):
        d=copy.deepcopy(self.good);d['cases'][0]['sample_count']=250
        with self.assertRaisesRegex(ValueError,'INVALID_WORKER_REPORT'):audit(d)
