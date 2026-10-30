"""C15 T3 P2B: ray integration, sparse blocks, negative evidence, independent parity."""
import math, random, unittest
from cognitum.proto import ray_occupancy_pb2 as p
from cognitum.spatial_ray_occupancy import integrate,RayRejected,_dda

def fixture():return p.RayBatch(schema_version=1,volume_id='vol',conversation_id='chat',voxel_size_m=1,max_axis=8,research_only=True)
def add(q,a=(.5,.5,.5),b=(3.5,.5,.5),hit=True,source='sensor',tick=1):
    return q.rays.add(start=p.Ray3(x=a[0],y=a[1],z=a[2]),end=p.Ray3(x=b[0],y=b[1],z=b[2]),endpoint_hit=hit,source_ref=source,tick=tick,hit_probability=.75,free_probability=.3)

class RayTests(unittest.TestCase):
    def test_axis_aligned_hit(self):
        q=fixture();add(q);r=integrate(q)
        self.assertEqual([(c.x,c.hit_count,c.free_count) for c in r.cells],[(0,0,1),(1,0,1),(2,0,1),(3,1,0)])
    def test_no_hit_full_range_free(self):
        q=fixture();add(q,hit=False)
        self.assertTrue(all(c.free_count==1 and c.hit_count==0 for c in integrate(q).cells))
    def test_three_dimensional_diagonal(self):
        q=fixture();add(q,b=(3.5,3.5,3.5));r=integrate(q)
        self.assertEqual([(c.x,c.y,c.z) for c in r.cells],[(i,i,i) for i in range(4)])
    def test_reversed_direction(self):
        q=fixture();add(q,a=(3.5,.5,.5),b=(.5,.5,.5))
        self.assertEqual([c.x for c in integrate(q).cells],[0,1,2,3])
    def test_duplicate_rays_same_source_tick_not_double_counted(self):
        q=fixture();add(q);add(q)
        self.assertEqual(sum(c.hit_count+c.free_count for c in integrate(q).cells),4)
    def test_conflicting_same_source_tick_rejected(self):
        q=fixture();add(q);add(q,hit=False)
        with self.assertRaisesRegex(RayRejected,'CONFLICT'):integrate(q)
    def test_different_sources_conflict_visible(self):
        q=fixture();add(q);add(q,hit=False,source='other')
        self.assertTrue(any(c.conflicted for c in integrate(q).cells))
    def test_unknown_unobserved_space_not_materialized(self):
        q=fixture();add(q)
        self.assertLess(len(integrate(q).cells),q.max_axis**3)
    def test_partial_multiresolution_never_complete(self):
        q=fixture();add(q)
        self.assertTrue(any(not x.complete and x.mean_probability==0 for x in integrate(q).coarse_blocks))
    def test_complete_two_cell_block_occupancy(self):
        q=fixture();t=1
        for x in (0,1):
          for y in (0,1):
           for z in (0,1):
            add(q,(x+.25,y+.5,z+.5),(x+.75,y+.5,z+.5),True,'s',t);t+=1
        result=integrate(q)
        c=next(c for c in result.coarse_blocks if c.level==2 and (c.x,c.y,c.z)==(0,0,0))
        self.assertEqual((c.observed_children,c.expected_children,c.complete),(8,8,True))
        self.assertAlmostEqual(c.mean_probability,.75)
    def test_edge_block_child_count(self):
        q=fixture();q.max_axis=3
        add(q,a=(2.25,2.5,2.5),b=(2.75,2.5,2.5))
        c=next(x for x in integrate(q).coarse_blocks if x.level==2 and (x.x,x.y,x.z)==(1,1,1))
        self.assertEqual(c.expected_children,1);self.assertTrue(c.complete)
    def test_reject_zero_length(self):
        q=fixture();add(q,a=(.5,.5,.5),b=(.5,.5,.5))
        with self.assertRaisesRegex(RayRejected,'ZERO_LENGTH_RAY'):integrate(q)
    def test_reject_nonfinite(self):
        q=fixture();add(q).end.x=float('nan')
        with self.assertRaises(RayRejected):integrate(q)
    def test_reject_out_of_bounds(self):
        q=fixture();add(q,b=(8.0,.5,.5))
        with self.assertRaises(RayRejected):integrate(q)
    def test_reject_unprovenanced(self):
        q=fixture();add(q).source_ref=''
        with self.assertRaises(RayRejected):integrate(q)
    def test_reject_uncalibrated_probability_domain(self):
        q=fixture();add(q).hit_probability=.1
        with self.assertRaises(RayRejected):integrate(q)
    def test_reject_authority(self):
        q=fixture();add(q);q.grants_authority=True
        with self.assertRaises(RayRejected):integrate(q)
    def test_unknown_fields_rejected(self):
        q=fixture();add(q)
        changed=p.RayBatch()
        changed.ParseFromString(q.SerializeToString()+b"\x80\x06\x01")
        with self.assertRaisesRegex(RayRejected,'UNKNOWN_PROTO_FIELDS'):integrate(changed)
    def test_preserve_input(self):
        q=fixture();add(q);wire=q.SerializeToString();integrate(q)
        self.assertEqual(q.SerializeToString(),wire)
    def test_independent_subvoxel_sampling_80_random_segments(self):
        rng=random.Random(15312)
        for k in range(80):
            a=tuple(rng.uniform(.1,7.9) for _ in range(3))
            b=tuple(rng.uniform(.1,7.9) for _ in range(3))
            d=_dda(a,b,1.,8)
            # Independent brute-force segment sampling, excluding measure-zero boundaries.
            oracle=[]
            for j in range(5001):
                t=j/5000
                c=tuple(math.floor(a[i]+(b[i]-a[i])*t) for i in range(3))
                if not oracle or oracle[-1]!=c:oracle.append(c)
            self.assertEqual(d,oracle,(k,a,b))

if __name__=='__main__':unittest.main()
