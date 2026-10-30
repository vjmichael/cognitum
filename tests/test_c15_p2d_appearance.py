import unittest
from cognitum.proto import spatial_appearance_pb2 as p
from cognitum.spatial_appearance_evidence import assess,AppearanceRejected

def spec():return p.AppearanceDescriptor(schema_version=1,model_id='mars-small128',image_source_id='camera_a',detection_id='frame1_det2',conversation_id='chat1',frame=1,encoder_sha256=b'1'*32,frame_sha256=b'2'*32,vector=[1.0]+[0.0]*127,research_only=True)

class AppearanceTests(unittest.TestCase):
 def test_structural_check_not_attestation(self):
    r=assess(spec());self.assertTrue(r.format_valid);self.assertFalse(r.independently_authenticated);self.assertFalse(r.grants_authority)
 def test_forged_hash_size(self):
    q=spec();q.frame_sha256=b'1'*31
    with self.assertRaises(AppearanceRejected):assess(q)
 def test_no_authority(self):
    q=spec();q.grants_authority=True
    with self.assertRaises(AppearanceRejected):assess(q)
 def test_invalid_vector(self):
    q=spec();q.vector[0]=float('nan')
    with self.assertRaises(AppearanceRejected):assess(q)
 def test_norm_required(self):
    q=spec();q.vector[0]=.5
    with self.assertRaises(AppearanceRejected):assess(q)

if __name__=='__main__':unittest.main()
