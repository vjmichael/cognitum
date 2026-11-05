"""C15 scene and tracking reference with real SciPy, adversarial identity cases."""
import math
import unittest
from dataclasses import replace

from cognitum.spatial_geometry import (
    Frame,SceneObject,Scene,validate as validate_scene,world_position,relation,
)
from cognitum.spatial_tracking import (
    Detection,Track,validate as validate_tracks,overlap,update,
)


def scene():
    return Scene(
        (Frame("camera","world",(2.,3.,4.),(0.,0.,0.,1.)),
         Frame("rig","camera",(1.,0.,0.),(0.,0.,0.,1.))),
        (SceneObject("cup","rig",(1.,2.,3.),(0.2,0.2,0.3),True,
                     "camera_observation",100,1),
         SceneObject("table","world",(5.,5.,7.),(1.,1.,1.),True,
                     "manual_placement",90,1)),
        101,
    )


class C15GeometryTests(unittest.TestCase):
    def test_world_coordinates_and_scene_relation(self):
        self.assertEqual(world_position(scene(),"cup"),(4.,5.,7.))
        r=relation(scene(),"cup","table")
        self.assertAlmostEqual(r["distance_m"],1)
        self.assertTrue(r["first_left_of_second"])
        self.assertEqual(r["frame"],"world")

    def test_quaternion_rotation_not_confused_with_translation(self):
        try:
            from scipy.spatial.transform import Rotation
        except ImportError:
            self.skipTest("SciPy unavailable")
        p=Scene((Frame("camera","world",(0.,0.,0.),
                       (0.,0.,math.sqrt(.5),math.sqrt(.5))),),
                (SceneObject("marker","camera",(1.,0.,0.),
                             (.1,.1,.1),True,"camera_observation",0),),0)
        x,y,z=world_position(p,"marker")
        self.assertAlmostEqual(x,0,places=6)
        self.assertAlmostEqual(y,1,places=6)
        self.assertAlmostEqual(z,0,places=6)

    def test_bad_frames_aliases_source_and_time(self):
        base=scene()
        cases=(
            replace(base,frames=(replace(base.frames[0],parent="rig"),base.frames[1])),
            replace(base,frames=(replace(base.frames[0],quaternion_xyzw=(0.,0.,0.,0.)),base.frames[1])),
            replace(base,objects=(base.objects[0],base.objects[0])),
            replace(base,objects=(replace(base.objects[0],frame="missing"),)),
            replace(base,objects=(replace(base.objects[0],observation_source=""),)),
            replace(base,objects=(replace(base.objects[0],timestamp_ms=102),)),
            replace(base,objects=(replace(base.objects[0],dimensions_m=(1.,0.,1.)),)),
            replace(base,objects=(replace(base.objects[0],position_m=(1.,math.nan,0.)),)),
        )
        for bad in cases:
            with self.subTest(bad=repr(bad)[:100]),self.assertRaises(ValueError):
                validate_scene(bad)


class C15TrackingTests(unittest.TestCase):
    def test_assignment_and_identity_preservation(self):
        tracks=(Track("alice",0.,0.,10.,10.,last_source="camera_a"),
                Track("bob",50.,0.,10.,10.,last_source="camera_a"))
        dets=(Detection("d_b",51.,0.,10.,10.,"camera_b"),
              Detection("d_a",1.,0.,10.,10.,"camera_b"))
        result=update(tracks,dets)
        self.assertEqual(result.assignments,(("alice","d_a"),("bob","d_b")))
        self.assertEqual(tuple(t.stable_id for t in result.tracks),("alice","bob"))
        self.assertEqual(tuple(t.missed for t in result.tracks),(0,0))
        self.assertEqual(result.unmatched_detections,())

    def test_occlusion_reappearance_and_retirement(self):
        t=(Track("object1",5.,5.,10.,10.),)
        missing=update(t,(),max_missed=2)
        self.assertEqual(missing.tracks[0].stable_id,"object1")
        self.assertEqual(missing.tracks[0].missed,1)
        regained=update(missing.tracks,
                        (Detection("det_7",5.5,5.5,10.,10.,"camera_a"),),
                        max_missed=2)
        self.assertEqual(regained.assignments,(("object1","det_7"),))
        self.assertEqual(regained.tracks[0].missed,0)
        terminal=update(update(t,(),max_missed=1).tracks,(),max_missed=1)
        self.assertEqual(terminal.retired_ids,("object1",))
        self.assertEqual(terminal.tracks,())

    def test_new_detections_not_given_invented_stable_ids(self):
        result=update((),(Detection("raw_1",1.,1.,5.,5.,"camera_a"),))
        self.assertEqual(result.tracks,())
        self.assertEqual(result.unmatched_detections,("raw_1",))

    def test_no_forced_distant_identity_swap(self):
        t=(Track("existing",0.,0.,2.,2.),)
        d=(Detection("far",100.,100.,2.,2.,"camera_a"),)
        result=update(t,d,max_distance=20)
        self.assertEqual(result.assignments,())
        self.assertEqual(result.unmatched_detections,("far",))
        self.assertEqual(result.tracks[0].missed,1)

    def test_bad_type_duplicate_ids_and_thresholds(self):
        t=(Track("a",0.,0.,2.,2.),)
        d=(Detection("x",0.,0.,2.,2.,"a"),)
        invalid=(
            (t+t,d), (t,d+d),
            ((replace(t[0],missed=-1),),d),
            ((replace(t[0],width=0),),d),
            (t,(replace(d[0],source=""),)),
        )
        for tracks,dets in invalid:
            with self.assertRaises(ValueError):
                validate_tracks(tracks,dets)
        for thresh in (-1,float("nan"),1.5):
            with self.assertRaises(ValueError):
                update(t,d,min_iou=thresh)
        self.assertAlmostEqual(overlap(t[0],d[0]),1)


if __name__=="__main__":
    unittest.main()
