"""Synthetic adversarial P2K tests: no source labels fed to association."""
import unittest
from cognitum import spatial_p2k_dense_identity as m

def raw_row(f, ident, x, y=0, w=4, h=10):
    return f'{f},{ident},{x},{y},{w},{h},1,-1,-1,-1\n'

def synth(points):
    data=''.join(raw_row(f, j, x) for f, xs in enumerate(points,1) for j,x in enumerate(xs))
    return m.parse_id_blind(data.encode(),num_frames=len(points))

class DenseIdentity(unittest.TestCase):
    def test_input_identity_stripping(self):
        raw=raw_row(1,0,10)+raw_row(2,0,12)
        changed=raw_row(1,100,10)+raw_row(2,200,12)
        a,rows=m.parse_id_blind(raw.encode(),num_frames=2)
        b,other=m.parse_id_blind(changed.encode(),num_frames=2)
        self.assertEqual(a,b)
        self.assertNotEqual(rows,other)
        self.assertFalse(hasattr(a[1][0],'track_id'))
        self.assertEqual(m.assign_all(a,num_frames=2,mode='position')[0],m.assign_all(b,num_frames=2,mode='position')[0])

    def test_six_limit_is_not_silently_lifted(self):
        a,_=synth([[10*i for i in range(7)]])
        with self.assertRaisesRegex(m.DenseAssociationRejected,'DENSITY_EXCEEDS_CAPACITY'):
            m.assign_all(a,num_frames=1,mode='position',params=m.Params(max_boxes=6))

    def test_seven_objects_supported_explicitly(self):
        a,_=synth([[10*i for i in range(7)],[10*i+2 for i in range(7)]])
        out,counts,_=m.assign_all(a,num_frames=2,mode='position')
        self.assertEqual(len(out[2]),7)
        self.assertEqual(counts['frames_over_legacy_six_observation_limit'],2)
        self.assertEqual(len(set(out[2])),7)

    def test_crossing_velocity_separates_direction_when_position_swaps(self):
        a,_=synth([[0,100],[30,70],[60,40],[90,10]])
        params=m.Params(sigma_px=35)
        pos,_,_=m.assign_all(a,num_frames=4,mode='position',params=params)
        vel,_,_=m.assign_all(a,num_frames=4,mode='velocity',params=params)
        self.assertNotEqual(pos[3][0],pos[1][0])
        self.assertEqual(vel[3][0],vel[1][0])
        self.assertEqual(vel[4][0],vel[1][0])

    def test_short_occlusion_preserves_identity_and_frame_time(self):
        a,_=synth([[0],[10],[],[],[],[50]])
        out,counts,_=m.assign_all(a,num_frames=6,mode='velocity')
        self.assertEqual(out[1],out[6]);self.assertEqual(counts['missing_frames_or_no_detections'],3)

    def test_long_occlusion_expires_identity(self):
        a,_=synth([[0],[10]]+[[]]*13+[[20]])
        out,_,_=m.assign_all(a,num_frames=16,mode='velocity')
        self.assertNotEqual(out[1],out[16])

    def test_changing_count_and_unique_per_frame(self):
        a,_=synth([[0],[1,100],[2,100,200],[3,102],[4]])
        out,c,_=m.assign_all(a,num_frames=5,mode='position')
        self.assertEqual([len(out[x]) for x in range(1,6)],[1,2,3,2,1])
        self.assertTrue(all(len(set(ids))==len(ids) for ids in out.values()))
        self.assertEqual(c['input_boxes'],9)

    def test_tampered_nonfinite_rejected(self):
        for value in ('nan','inf','-1'):
            with self.subTest(value=value),self.assertRaises(m.DenseAssociationRejected):
                m.parse_id_blind(raw_row(1,1,10,w=value).encode(),num_frames=1)

    def test_stale_frames_rejected(self):
        a,_=synth([[0],[2]])
        with self.assertRaisesRegex(m.DenseAssociationRejected,'INVALID_DETECTION'):
            m.assign_all({2:a[1]},num_frames=2,mode='position')

    def test_config_fails_closed(self):
        a,_=synth([[0]])
        for p in (m.Params(sigma_px=float('nan')),m.Params(max_gap_frames=0),m.Params(max_tracks=0)):
            with self.subTest(params=p),self.assertRaises(m.DenseAssociationRejected):
                m.assign_all(a,num_frames=1,mode='position',params=p)

if __name__=='__main__': unittest.main()
