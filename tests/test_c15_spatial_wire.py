"""C15 native typed scene and tracking protocol tests."""
from hashlib import sha256
import unittest

from cognitum.proto import spatial_core_pb2 as pb
from cognitum.spatial_core_wire import (
    execute_scene,execute_track,verify_scene,verify_track,
)


def scene_frame():
    q=pb.SceneQuery(schema_version=1,epoch=101,object_id="cup",reference_id="table")
    q.frames.add(name="camera",parent="world",
                 translation_m=[1.,2.,3.],quaternion_xyzw=[0.,0.,0.,1.])
    q.objects.add(stable_id="cup",frame="camera",position_m=[1.,0.,0.],
                  dimensions_m=[.2,.2,.3],visible=True,
                  observation_source="camera_observation",timestamp_ms=100,version=1)
    q.objects.add(stable_id="table",frame="world",position_m=[5.,2.,3.],
                  dimensions_m=[1.,1.,1.],visible=True,
                  observation_source="manual_placement",timestamp_ms=99,version=1)
    return q.SerializeToString(deterministic=True)


def track_frame():
    q=pb.TrackRequest(schema_version=1,min_iou=0.05,max_distance=20,max_missed=3)
    q.tracks.add(stable_id="existing",x=0,y=0,width=10,height=10,missed=1,
                 last_source="camera_a")
    q.detections.add(detection_id="det1",x=1,y=1,width=10,height=10,
                     source="camera_b")
    q.detections.add(detection_id="far",x=100,y=100,width=10,height=10,
                     source="camera_b")
    return q.SerializeToString(deterministic=True)


class C15WireTests(unittest.TestCase):
    def test_real_scipy_geometry_roundtrip(self):
        try:import scipy
        except ImportError:self.skipTest("SciPy not installed")
        request=scene_frame()
        result=verify_scene(request,execute_scene(request))
        self.assertEqual(result.status,"OK")
        self.assertEqual(tuple(result.world_position_m),(2.,2.,3.))
        self.assertAlmostEqual(result.distance_m,3)
        self.assertEqual(result.request_sha256,sha256(request).hexdigest())

    def test_real_hungarian_association_roundtrip(self):
        try:import scipy
        except ImportError:self.skipTest("SciPy not installed")
        request=track_frame()
        result=verify_track(request,execute_track(request))
        self.assertEqual(result.status,"ASSOCIATED")
        self.assertEqual(len(result.matches),1)
        self.assertEqual(result.matches[0].stable_id,"existing")
        self.assertEqual(result.matches[0].detection_id,"det1")
        self.assertEqual(tuple(result.unmatched_detections),("far",))

    def test_forged_identity_and_geometry_refused(self):
        request=track_frame()
        result=pb.TrackResult()
        result.ParseFromString(execute_track(request))
        result.matches[0].stable_id="other"
        with self.assertRaises(ValueError):
            verify_track(request,result.SerializeToString(deterministic=True))
        request=scene_frame()
        obj=pb.SceneResult()
        obj.ParseFromString(execute_scene(request))
        obj.distance_m=0
        with self.assertRaises(ValueError):
            verify_scene(request,obj.SerializeToString(deterministic=True))

    def test_bad_unknown_repeated_wire(self):
        request=scene_frame()
        for invalid in (b"",request+b"\x98\x06\x01",request+b"\x08\x01",
                        b"\x0a\xff",b"f"*65537):
            with self.subTest(frame=invalid[:10]),self.assertRaises(ValueError):
                execute_scene(invalid)
        q=pb.SceneQuery()
        q.ParseFromString(request)
        q.objects[0].timestamp_ms=200
        with self.assertRaises(ValueError):
            execute_scene(q.SerializeToString(deterministic=True))

    def test_typed_no_capture_or_host_permissions(self):
        for cls in (pb.SceneQuery,pb.TrackRequest):
            fields={f.name for f in cls.DESCRIPTOR.fields}
            for forbidden in ("image_bytes","video_path","camera_open","python",
                              "shell","host_permission","grants"):
                self.assertNotIn(forbidden,fields)


if __name__=="__main__":
    unittest.main()
