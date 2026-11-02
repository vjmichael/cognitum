"""Independent-from-runner evidence audit for CH25; does not modify frozen datasets.

The audit checks CH23 source regeneration, exact binary64->decimal serialization,
input/certificate/protocol SHA binding, covering proof tree, and saved 224-bit
replay receipts. It is not a second formal proof of interval-arithmetic code;
replay_B.py re-executes leaf bounds at higher MPFR precision.
"""
import json,hashlib,sys,pathlib,copy,unittest
from decimal import Decimal
P=pathlib.Path(__file__).resolve().parent
C23=P.parent/'ch_c14_23';C24=P.parent/'ch_c14_24'
if not C23.exists():C23=pathlib.Path('/mnt/data/recovered_ch23/CH_C14_23')
if not C24.exists():C24=pathlib.Path('/mnt/data/CH_C14_24')
sys.path.insert(0,str(C23));import run as ch23_run
sys.path.insert(0,str(C24));from verify_certificate import check_tree
B=json.loads((P/'frozen_protocol_B.json').read_text());proto_sha=hashlib.sha256((P/'frozen_protocol_B.json').read_bytes()).hexdigest()
assert proto_sha==(P/'frozen_protocol_B.sha256').read_text().split()[0]
R={(r['family'],r['n'],r['index']):r for r in map(json.loads,(C23/'results.jsonl').read_text().splitlines())}
class ProvenanceAudit(unittest.TestCase):
 def test_original_case_identities(self):
  self.assertEqual(len(B['cases']),15)
  self.assertEqual(len({x['id'] for x in B['cases']}),15)
  self.assertEqual(sum(c['ambiguous'] for c in B['cases']),3)
 def test_full_evidence_chain(self):
  for c in B['cases']:
   with self.subTest(c['id']):
    r=R[c['family'],c['n'],c['index']];self.assertEqual(c['original_digest'],r['data_digest'])
    x,y=ch23_run.generator(c['family'],c['n'],c['seed'])
    self.assertEqual(hashlib.sha256(x.tobytes()+y.tobytes()).hexdigest(),c['original_digest'])
    input_bytes=(P/'inputs'/(c['id']+'.json')).read_bytes();self.assertEqual(hashlib.sha256(input_bytes).hexdigest(),c['exact_input_sha256'])
    inp=json.loads(input_bytes)
    self.assertEqual(len(inp['rows']),c['n'])
    for xrow,yy,inrow in zip(x,y,inp['rows']):
     self.assertEqual(tuple(Decimal.from_float(float(v)) for v in xrow),tuple(Decimal(z) for z in inrow['x']))
     self.assertEqual(int(yy),inrow['y'])
    cert=json.loads((P/'certificates'/(c['id']+'.json')).read_text())
    self.assertEqual(cert['CH25_original_case']['original_digest'],c['original_digest'])
    self.assertEqual(cert['CH25_original_case']['frozen_input_sha256'],c['exact_input_sha256'])
    self.assertEqual(cert['CH25_original_case']['protocol_B_sha256'],proto_sha)
    self.assertEqual(cert['status'],'UNRESOLVED_REFUSE_CERTIFICATION')
    self.assertEqual(cert['claim_scope'],'finite_root_box_only')
    self.assertEqual(len(cert['nodes']),31)
    self.assertEqual(len(check_tree(cert['nodes'],cert['root_box'])),16)
    v=json.loads((P/'verifications'/(c['id']+'.json')).read_text())
    self.assertEqual(v['result'],'REPLAYED_BUT_UNRESOLVED')
    self.assertEqual(v['original_digest'],c['original_digest'])
    self.assertTrue(v['partition_cover_verified'] and v['all_leaf_bounds_recomputed'])
    self.assertGreater(v['absolute_gap_upper_display'],float(B['objective_absolute_tolerance']))
    if c['id']!='quasi_separated_n160_i00':
     log=json.loads((P/'logs'/(c['id']+'.json')).read_text())
     self.assertEqual(log['verifier_result'],v['result'])
     root=log.get('root_evidence',log)
     self.assertEqual(root.get('root_basic_up',root.get('root_basic_upper')),root.get('root_curvature_up',root.get('root_curvature_upper')))
 def test_replay_rejects_partition_tamper(self):
  f=P/'certificates'/'zero_balanced_n80_i00.json'
  cert=json.loads(f.read_text())
  tampered=copy.deepcopy(cert['nodes']);tampered[0]['children']=[1,1]
  with self.assertRaises(ValueError):check_tree(tampered,cert['root_box'])
  tampered=copy.deepcopy(cert['nodes']);tampered[1]['box'][0][0]='-9.999'
  with self.assertRaises(ValueError):check_tree(tampered,cert['root_box'])
if __name__=='__main__':unittest.main(verbosity=2)
