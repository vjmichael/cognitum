"""T3 P2C: explicit frames, temporal evidence, holdout scores, fail-closed cases."""
import math,unittest
from cognitum.proto import temporal_occupancy_pb2 as pb
from cognitum.spatial_temporal_occupancy import integrate,TemporalOccupancyRejected,_rotate

def fixture():
 q=pb.TemporalOccupancyRequest(schema_version=1,conversation_id='chat',volume_id='volume',voxel_size_m=1,max_axis=16,evaluation_tick=10,half_life_ticks=5,research_only=True)
 f=q.frames.add(frame_id='world',qw=1);f.translation.x=f.translation.y=f.translation.z=0
 ray(q)
 return q

def ray(q, tick=10, source='laser', start=(.1,.1,.1),end=(2.1,.1,.1),hit=True,frame='world'):
 r=q.rays.add(source_ref=source,tick=tick,frame_id=frame,endpoint_hit=hit,hit_probability=.8,free_probability=.3)
 for o,xyz in [(r.start,start),(r.end,end)]:o.x,o.y,o.z=xyz
 return r

class TemporalOccupancyTests(unittest.TestCase):
 def test_empty_cells_unknown(self):
  x=integrate(fixture());self.assertEqual(len(x.cells),3);self.assertFalse(x.grants_authority)
 def test_probabilities(self):
  x=integrate(fixture());cells={(c.x,c.y,c.z):c.probability for c in x.cells};self.assertAlmostEqual(cells[(2,0,0)],.8);self.assertAlmostEqual(cells[(0,0,0)],.3)
 def test_old_evidence_discount(self):
  q=fixture();q.rays[0].tick=5;v=integrate(q);self.assertAlmostEqual(next(c for c in v.cells if c.x==2).log_odds,math.log(4)*.5)
 def test_contradiction_visible(self):
  q=fixture();ray(q,source='camera',start=(2.1,.1,.1),end=(3.1,.1,.1));x=integrate(q);self.assertTrue(next(c for c in x.cells if c.x==2).conflicted)
 def test_duplicate_same_tick_source_rejected(self):
  q=fixture();ray(q);self.assertRaises(TemporalOccupancyRejected,integrate,q)
 def test_future_tick(self):
  q=fixture();q.rays[0].tick=12;self.assertRaises(TemporalOccupancyRejected,integrate,q)
 def test_bad_frame(self):
  q=fixture();q.frames[0].qw=2;self.assertRaises(TemporalOccupancyRejected,integrate,q)
 def test_missing_frame(self):
  q=fixture();q.rays[0].frame_id='missing';self.assertRaises(TemporalOccupancyRejected,integrate,q)
 def test_invalid_half_life(self):
  q=fixture();q.half_life_ticks=0;self.assertRaises(TemporalOccupancyRejected,integrate,q)
 def test_nan_sensor(self):
  q=fixture();q.rays[0].hit_probability=float('nan');self.assertRaises(TemporalOccupancyRejected,integrate,q)
 def test_nan_position(self):
  q=fixture();q.rays[0].end.x=float('nan');self.assertRaises(TemporalOccupancyRejected,integrate,q)
 def test_authority(self):
  q=fixture();q.grants_authority=True;self.assertRaises(TemporalOccupancyRejected,integrate,q)
 def test_proto_unknown_fields(self):
  q=fixture();other=pb.TemporalOccupancyRequest.FromString(q.SerializeToString()+b'\xd8\x07\x01')
  self.assertRaises(TemporalOccupancyRejected,integrate,other)
 def test_holdout_brier(self):
  q=fixture();q.holdout_labels.add(x=2,y=0,z=0,occupied=True,source_ref='separate');q.holdout_labels.add(x=0,y=0,z=0,occupied=False,source_ref='separate')
  x=integrate(q);self.assertEqual(x.holdout.evaluated_count,2);self.assertAlmostEqual(x.holdout.brier_score,(.2**2+.3**2)/2);self.assertIn('NOT_AUTHENTICATED',x.holdout.assessment)
 def test_holdout_unseen_rejected(self):
  q=fixture();q.holdout_labels.add(x=12,y=0,z=0,occupied=True,source_ref='truth');self.assertRaises(TemporalOccupancyRejected,integrate,q)
 def test_duplicate_label_rejected(self):
  q=fixture();[q.holdout_labels.add(x=2,y=0,z=0,occupied=True,source_ref='truth') for _ in range(2)]
  self.assertRaises(TemporalOccupancyRejected,integrate,q)
 def test_coordinate_registration_translation(self):
  q=fixture();q.frames[0].translation.x=2;v=integrate(q);self.assertEqual([c.x for c in v.cells],[2,3,4])
 def test_coordinate_registration_quaternion(self):
  q=fixture();f=q.frames[0];f.qw=math.sqrt(.5);f.qz=math.sqrt(.5);f.translation.x=1;v=integrate(q)
  self.assertEqual(sorted((c.x,c.y) for c in v.cells),[(0,0),(0,1),(0,2)])
 def test_against_scipy_rotation(self):
  import numpy as np
  from scipy.spatial.transform import Rotation
  q=(math.cos(.42),.1,.2,0)
  n=math.sqrt(sum(v*v for v in q));q=tuple(v/n for v in q)
  v=(1.2,-.1,3.1)
  expected=Rotation.from_quat([q[1],q[2],q[3],q[0]]).apply(v)
  np.testing.assert_allclose(_rotate(q,v),expected,rtol=0,atol=1e-12)
 def test_two_frames_same_world_cell(self):
  q=fixture();q.frames.add(frame_id='offset',qw=1).translation.x=2
  ray(q,tick=9,source='second',start=(-1.9,.1,.1),end=(.1,.1,.1),frame='offset')
  x=integrate(q);self.assertEqual(len(x.cells),3)
 def test_zero_length_rejected(self):
  q=fixture();q.rays[0].end.CopyFrom(q.rays[0].start);self.assertRaises(TemporalOccupancyRejected,integrate,q)

 def test_calibration_fit_separate_holdout(self):
  q=fixture()
  q.calibration_labels.add(x=0,y=0,z=0,occupied=True,source_ref='train_truth')
  q.holdout_labels.add(x=2,y=0,z=0,occupied=True,source_ref='holdout_truth')
  result=integrate(q)
  self.assertEqual(result.holdout.training_count,1)
  self.assertEqual(result.holdout.evaluated_count,1)
  self.assertGreater(result.holdout.selected_temperature,1)
  self.assertNotEqual(result.holdout.calibrated_brier,result.holdout.brier_score)
 def test_calibration_label_leakage_rejected(self):
  q=fixture()
  q.calibration_labels.add(x=2,y=0,z=0,occupied=True,source_ref='train')
  q.holdout_labels.add(x=2,y=0,z=0,occupied=True,source_ref='test')
  self.assertRaises(TemporalOccupancyRejected,integrate,q)
 def test_unseen_calibration_label_rejected(self):
  q=fixture();q.calibration_labels.add(x=6,y=0,z=0,occupied=True,source_ref='train')
  self.assertRaises(TemporalOccupancyRejected,integrate,q)

if __name__=='__main__':unittest.main()
