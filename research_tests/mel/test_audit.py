"""Offline metadata qualification; no research execution or admission."""
import copy
import json
from pathlib import Path
import unittest
from tools.mel import audit

ROOT=Path(__file__).resolve().parents[2]


class ReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs=audit.read_documents(ROOT)
        cls.baseline=json.loads((ROOT/audit.DOCS/'BASELINE.json').read_text(encoding='utf8'))
        cls.legacy=json.loads((ROOT/audit.LEGACY).read_text(encoding='utf8'))

    def compile(self, *, master=None, reconciliation=None, legacy=None, baseline=None):
        return audit.compile_inventory(self.docs['MASTER_REGISTER.md'] if master is None else master,
            self.docs['RECONCILIATION.md'] if reconciliation is None else reconciliation,
            self.legacy if legacy is None else legacy,self.baseline if baseline is None else baseline)

    def test_full_counts(self):
        r=self.compile()
        self.assertEqual(len(r['groups']),164)
        self.assertEqual(r['counts'],{'H':{'B':16,'P':36,'A':3,'O':5},'K':{'B':1,'P':10,'A':25,'O':24},
            'S':{'B':11,'P':9,'A':1,'O':3},'I-':{'P':1,'A':3,'O':16}})

    def test_no_authority(self):
        r=self.compile()
        self.assertFalse(r['mel_admission']);self.assertFalse(r['production_enabled'])
        self.assertEqual(len(r['reserved_operations']),11)
        for op in r['reserved_operations']:
            self.assertIs(op['executable'],False);self.assertIs(op['model_advertised'],False)
        for row in r['groups']:
            self.assertEqual(row['mel_admission'],'not_admitted');self.assertIs(row['production_enabled'],False)

    def test_legacy_namespaces(self):
        r=self.compile();self.assertEqual(len(r['legacy_links']),85)
        self.assertNotIn('H12',r['legacy_links']['H12'])
        self.assertIn('I-19',r['legacy_links']['H12'])
        self.assertIn('H25',audit.EXPECTED)

    def test_missing_master_group(self):
        with self.assertRaises(ValueError):self.compile(master=self.docs['MASTER_REGISTER.md'].replace('**H2 —','**H200 —',1))

    def test_missing_reconciliation_group(self):
        s='\n'.join(l for l in self.docs['RECONCILIATION.md'].splitlines() if not l.startswith('| H2 |'))
        with self.assertRaises(ValueError):self.compile(reconciliation=s)

    def test_duplicate_reconciliation_group(self):
        s=self.docs['RECONCILIATION.md'];row=next(l for l in s.splitlines() if l.startswith('| H2 |'))
        with self.assertRaises(ValueError):self.compile(reconciliation=s+'\n'+row)

    def test_bad_status(self):
        s=self.docs['RECONCILIATION.md'];row=next(l for l in s.splitlines() if l.startswith('| H2 |'))
        cols=row.split('|');cols[3]=' accepted ';bad='|'.join(cols)
        with self.assertRaises(ValueError):self.compile(reconciliation=s.replace(row,bad))

    def test_missing_legacy(self):
        legacy=copy.deepcopy(self.legacy);legacy['entries'].pop()
        with self.assertRaises(ValueError):self.compile(legacy=legacy)

    def test_legacy_method_change(self):
        legacy=copy.deepcopy(self.legacy);legacy['entries'][0]['method']='unreviewed replacement'
        with self.assertRaises(ValueError):self.compile(legacy=legacy)

    def test_legacy_evidence_evolves(self):
        legacy=copy.deepcopy(self.legacy);legacy['entries'][0]['status']='new_evidence_pending_review'
        self.assertEqual(self.compile(legacy=legacy)['legacy_links'],self.compile()['legacy_links'])

    def test_missing_source(self):
        baseline=copy.deepcopy(self.baseline);baseline['source_git_blobs'].pop(audit.BOUNDARY[0])
        with self.assertRaises(ValueError):self.compile(baseline=baseline)

    def test_wrong_baseline(self):
        baseline=copy.deepcopy(self.baseline);baseline['baseline_sha']='0'*40
        with self.assertRaises(ValueError):self.compile(baseline=baseline)


if __name__=='__main__':unittest.main()
