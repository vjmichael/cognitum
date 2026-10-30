import hashlib
import io
import json
import unittest
import numpy as np
from cognitum.proto import research_optional_pb2 as pb
from cognitum.research.hdc_optional import query,bound
from cognitum.research.kan_optional import ResearchPolicy,predict


def kan_artifact():
    buf=io.BytesIO()
    meta={'format':'zogzoo-kan-v3-npz','version':1,
          'layers':[{'kind':'rbf','degree':0,'base':False,'bias':False}]}
    np.savez_compressed(buf,__meta_json__=np.asarray(json.dumps(meta)),
        l0_grid=np.asarray([[-1,0,1]],dtype=np.float32),
        l0_spline=np.ones((1,1,3),dtype=np.float32),
        l0_mask=np.ones((1,1),dtype=np.float32))
    return buf.getvalue()

class HdcOptionalTests(unittest.TestCase):
    def req(self,**kw):
        r=pb.HdcQuery(schema_version=1,source_snapshot_id='v1',index_snapshot_id='v1',
                role='owns',entity='ship',top_k=2)
        for id,role,entity in [('r1','owns','ship'),('r2','owns','station'),('r3','visits','ship')]:
            r.records.add(candidate_id=id,role=role,entity=entity)
        for k,v in kw.items():setattr(r,k,v)
        return r.SerializeToString(deterministic=True)
    def test_hamming_bsc_binding_is_self_inverse(self):
        self.assertEqual(bound('owns','ship')^bound('owns','ship'),0)
        self.assertEqual((bound('owns','ship')^bound('owns','station')).bit_length()<=256,True)
    def test_query_candidates_only(self):
        res=pb.HdcCandidates.FromString(query(self.req()))
        self.assertEqual(res.candidate_ids[0],'r1')
        self.assertEqual(res.hamming_distance[0],0)
        self.assertFalse(res.grants_authority)
        self.assertEqual(res.source_snapshot_id,'v1')
    def test_reject_stale_snapshot(self):
        with self.assertRaisesRegex(ValueError,'STALE_INDEX'):query(self.req(index_snapshot_id='old'))
    def test_reject_duplicate_candidate(self):
        r=pb.HdcQuery.FromString(self.req());r.records.add(candidate_id='r1',role='owns',entity='moon')
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):query(r.SerializeToString())
    def test_reject_unknown_proto_field(self):
        with self.assertRaisesRegex(ValueError,'NONCANONICAL'):query(self.req()+b'\x98\x06\x01')
    def test_reject_invalid_query_and_budgets(self):
        with self.assertRaises(ValueError):query(self.req(top_k=9))
        with self.assertRaises(ValueError):query(self.req(role='bad /role'))
    def test_determinism(self):self.assertEqual(query(self.req()),query(self.req()))

class KanOptionalTests(unittest.TestCase):
    def setUp(self):
        self.checkpoint=kan_artifact();self.digest=hashlib.sha256(self.checkpoint).hexdigest()
        self.policy=ResearchPolicy(True,self.digest)
    def req(self,values=None,digest=None):
        return pb.KanRequest(schema_version=1,feature_values=['0'] if values is None else values,
             checkpoint_sha256=self.digest if digest is None else digest).SerializeToString(deterministic=True)
    def test_real_portable_k4_inference(self):
        res=pb.KanPrediction.FromString(predict(self.req(),self.checkpoint,self.policy))
        self.assertEqual(res.checkpoint_sha256,self.digest)
        self.assertEqual(len(res.predicted_values),1)
        self.assertGreater(float(res.predicted_values[0]),1)
        self.assertFalse(res.grants_authority or res.uncertainty_calibrated)
        self.assertIn('APPROXIMATE',res.limitation)
    def test_default_off(self):
        with self.assertRaises(PermissionError):predict(self.req(),self.checkpoint,ResearchPolicy())
    def test_wrong_checkpoint_pin(self):
        with self.assertRaisesRegex(ValueError,'PIN_MISMATCH'):
            predict(self.req(),self.checkpoint+b'x',self.policy)
        with self.assertRaisesRegex(ValueError,'PIN_MISMATCH'):
            predict(self.req(digest='0'*64),self.checkpoint,self.policy)
    def test_out_of_domain_refused(self):
        with self.assertRaisesRegex(ValueError,'OUT_OF_DISTRIBUTION'):
            predict(self.req(values=['200']),self.checkpoint,self.policy)
    def test_nonfinite_refused(self):
        with self.assertRaisesRegex(ValueError,'INVALID_FEATURES'):
            predict(self.req(values=['NaN']),self.checkpoint,self.policy)
    def test_unknown_proto_field_refused(self):
        with self.assertRaisesRegex(ValueError,'NONCANONICAL'):
            predict(self.req()+b'\x98\x06\x01',self.checkpoint,self.policy)
    def test_invalid_checkpoint_refused(self):
        fake=b'X'*4096
        with self.assertRaisesRegex(ValueError,'INVALID_CHECKPOINT_ZIP'):
            predict(self.req(digest=hashlib.sha256(fake).hexdigest()),fake,
                   ResearchPolicy(True,hashlib.sha256(fake).hexdigest()))
    def test_oversized_checkpoint_refused(self):
        fake=b'X'*131073
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_SIZE_LIMIT'):
            predict(self.req(digest=hashlib.sha256(fake).hexdigest()),fake,
                   ResearchPolicy(True,hashlib.sha256(fake).hexdigest()))
if __name__=='__main__':unittest.main()
