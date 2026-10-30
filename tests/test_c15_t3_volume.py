import unittest
from cognitum.proto import spatial_volume_pb2 as p
from cognitum.spatial_volume import classify,lookup,VolumeRejected

def fixture():return p.VolumeGrid(schema_version=1,volume_id='shell',conversation_id='thread',voxel_size_m=0.1,max_axis=10,research_only=True)

def add(g,coord,kind,source='lidar',tick=1,reliability=.9):
 return g.evidence.add(x=coord[0],y=coord[1],z=coord[2],kind=kind,source_id=source,tick=tick,reliability=reliability)

class VolumeTests(unittest.TestCase):
 def test_unknown_without_evidence(self):
    self.assertEqual(lookup(classify(fixture()),3,3,3),p.CELL_UNKNOWN)
 def test_shell_void_and_unknown(self):
    g=fixture();add(g,(1,1,1),p.VOLUME_MEASURED_OCCUPIED);add(g,(2,1,1),p.VOLUME_MEASURED_FREE)
    r=classify(g)
    self.assertEqual([lookup(r,x,1,1) for x in (1,2,3)],[p.CELL_OCCUPIED,p.CELL_FREE,p.CELL_UNKNOWN])
 def test_predicted_solid_does_not_become_fact(self):
    g=fixture();add(g,(2,2,2),p.VOLUME_PREDICTED_OCCUPIED)
    r=classify(g);self.assertEqual(lookup(r,2,2,2),p.CELL_UNKNOWN)
    self.assertEqual(r.cells[0].hypothesis_count,1)
 def test_conflict_fails_conservatively(self):
    g=fixture();add(g,(2,2,2),p.VOLUME_MEASURED_FREE,'sensorA');add(g,(2,2,2),p.VOLUME_MEASURED_OCCUPIED,'sensorB')
    self.assertEqual(lookup(classify(g),2,2,2),p.CELL_CONFLICTED)
 def test_latest_per_source_no_vote_stuffing(self):
    g=fixture();add(g,(2,2,2),p.VOLUME_MEASURED_OCCUPIED,tick=1);add(g,(2,2,2),p.VOLUME_MEASURED_FREE,tick=2)
    self.assertEqual(lookup(classify(g),2,2,2),p.CELL_FREE)
 def test_duplicate_tick_rejected(self):
    g=fixture();add(g,(1,1,1),p.VOLUME_MEASURED_FREE);add(g,(1,1,1),p.VOLUME_MEASURED_FREE)
    with self.assertRaisesRegex(VolumeRejected,'REPEATED'):classify(g)
 def test_out_of_bounds(self):
    g=fixture();add(g,(-1,0,0),p.VOLUME_MEASURED_FREE)
    with self.assertRaisesRegex(VolumeRejected,'BOUNDS'):classify(g)
 def test_nonfinite_reliability(self):
    g=fixture();add(g,(1,1,1),p.VOLUME_MEASURED_FREE,reliability=float('nan'))
    with self.assertRaises(VolumeRejected):classify(g)
 def test_no_authority(self):
    g=fixture();g.grants_authority=True
    with self.assertRaises(VolumeRejected):classify(g)
 def test_source_claim_not_authenticated(self):
    g=fixture();add(g,(2,2,2),p.VOLUME_MEASURED_OCCUPIED)
    self.assertIn('MEASURED_IS_CALLER_ASSERTION_NOT_AUTHENTICATION',classify(g).warnings)

if __name__=='__main__':unittest.main()
