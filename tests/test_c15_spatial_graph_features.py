"""C15 derived scene graph relation invalidation and source-scoped features."""
from dataclasses import replace
from hashlib import sha256
import unittest
from io import BytesIO

from cognitum.spatial_geometry import Scene,SceneObject
from cognitum.spatial_scene_graph import graph_relations,edge_still_current
from cognitum.spatial_tracking import Track,Detection
from cognitum.spatial_appearance_core import Appearance,validate_descriptors
from cognitum.spatial_cv_features import from_frame


def scene():
    return Scene((),(
        SceneObject("a","world",(0.,0.,0.),(.5,.5,.5),True,"source_a",3,1),
        SceneObject("b","world",(.5,0.,1.),(.5,.5,.5),True,"source_b",3,1),
    ),4)


class C15GraphAndFeatureTests(unittest.TestCase):
    def test_relation_edges_versioned_and_invalidated(self):
        base=scene()
        edges=graph_relations(base,near_m=2)
        self.assertTrue(any(e.predicate=="world_z_below" and e.subject_id=="a"
                            and e.object_id=="b" for e in edges))
        self.assertTrue(any(e.predicate=="near" and e.subject_id=="a"
                            and e.object_id=="b" for e in edges))
        for e in edges:
            self.assertTrue(edge_still_current(base,e))
            self.assertEqual(e.coordinate_frame,"world")
            self.assertEqual(set(e.evidence_sources),{"source_a","source_b"})
        updated=replace(base,objects=(replace(base.objects[0],version=2),base.objects[1]))
        self.assertFalse(edge_still_current(updated,edges[0]))
        hidden=replace(base,objects=(replace(base.objects[0],visible=False),base.objects[1]))
        self.assertFalse(edge_still_current(hidden,edges[0]))
        with self.assertRaises(ValueError):
            graph_relations(base,near_m=float("nan"))

    def test_image_digest_is_not_identity_authentication(self):
        try:
            from PIL import Image
            import cv2
        except ImportError:
            self.skipTest("OpenCV/Pillow unavailable")
        im=Image.new("RGB",(16,16),(0,255,0))
        out=BytesIO()
        im.save(out,format="PNG")
        frame=out.getvalue()
        result=from_frame(frame,source_id="src",observation_id="obs1",
            detection_id="detection_one",frame_index=9,box=(0,0,16,16),
            host_admitted=True)
        self.assertEqual(result.image_sha256,sha256(frame).hexdigest())
        self.assertEqual(len(result.vector),128)
        bad=replace(result,image_sha256="not-a-digest")
        tracks=(Track("track_one",0,0,16,16),)
        dets=(Detection("detection_one",0,0,16,16,"src"),)
        with self.assertRaises(ValueError):
            validate_descriptors(tracks,dets,(bad,))
        with self.assertRaises(ValueError):
            validate_descriptors((Track("same",0,0,10,10),),
                (Detection("same",0,0,10,10,"src"),),(result,))


if __name__=="__main__":
    unittest.main()
