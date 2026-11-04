"""C15 durable scene recovery, identity evaluation and optional CV evidence."""
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitum.spatial_geometry import SceneObject,Scene,world_pose,Frame
from cognitum.spatial_lifecycle import Evidence,Entity,SceneRevision,SceneMutation,mutate
from cognitum.spatial_scene_journal import SceneJournal,encode,decode
from cognitum.spatial_tracking import Track,Detection
from cognitum.spatial_appearance_core import Appearance
from cognitum.spatial_identity_eval import EvalFrame,evaluate,compare
from cognitum.spatial_cv_features import from_frame

DIGEST="a"*64

def evidence(name):
    return Evidence("source",name,10,0.9,"world","manual_annotation",
                    "authorization_record",DIGEST)

def base():
    obj=SceneObject("subject","world",(0.,0.,0.),(1.,1.,1.),
                    True,"source",10,1,geometry_ref="asset:mesh001",confidence=.9)
    return SceneRevision("scene1",0,(),(Entity(obj,(),(evidence("initial"),),"visible"),),
                         100,())

def descriptor(identity,vector):
    return Appearance(identity,tuple(vector),"approved_encoder",DIGEST,
                      "source","observation_"+identity,1)


class C15ExtendedTests(unittest.TestCase):
    def test_full_world_pose(self):
        try:
            from scipy.spatial.transform import Rotation
        except ImportError:
            self.skipTest("SciPy not installed")
        q=tuple(float(x) for x in Rotation.from_euler("z",90,degrees=True).as_quat())
        scene=Scene((Frame("camera","world",(1.,2.,0.),q),),
            (SceneObject("subject","camera",(1.,0.,0.),(1.,1.,1.),
                         True,"source",10,1,q,"asset:mesh001",.8),),11)
        xyz,rotation=world_pose(scene,"subject")
        self.assertAlmostEqual(xyz[0],1,places=8)
        self.assertAlmostEqual(xyz[1],3,places=8)
        self.assertAlmostEqual(rotation[2],1,places=8)
        self.assertAlmostEqual(rotation[3],0,places=8)

    def test_canonical_snapshot_restore_restart_and_cas(self):
        original=base()
        self.assertEqual(decode(encode(original)),original)
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"scene.sqlite"
            db=SceneJournal(path)
            db.put(original,expected_previous=-1)
            change=SceneMutation("mutation_1","subject","occlude",1,
                                 evidence=evidence("occlusion"))
            newer=mutate(original,change,expected_revision=0,
                         admitted_by_trusted_host=True)
            db.put(newer,expected_previous=0)
            with self.assertRaises(ValueError):
                db.put(newer,expected_previous=0)
            db.close()
            reopened=SceneJournal(path)
            self.assertEqual(reopened.restore("scene1"),newer)
            reopened.close()
            self.assertEqual(newer.entities[0].obj.stable_id,"subject")
            self.assertEqual(newer.entities[0].state,"occluded")

    def test_corrupt_payload_and_chain_fail_closed(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"scene.sqlite"
            db=SceneJournal(path)
            db.put(base(),expected_previous=-1)
            db.db.execute("UPDATE scene_revisions SET payload_sha256=?",
                          ("0"*64,))
            with self.assertRaises(ValueError):
                db.restore("scene1")
            db.close()
        with self.assertRaises(ValueError):
            decode(b'{"schema":3}')

    def test_evaluation_truth_not_used_as_associator_input(self):
        t=(Track("a",0,0,10,10),Track("b",30,0,10,10))
        d=(Detection("da",1,0,10,10,"source"),
           Detection("db",31,0,10,10,"source"))
        frame=EvalFrame(t,d,(("a","da"),("b","db")),(
            descriptor("a",(1,0)),descriptor("b",(0,1)),
            descriptor("da",(1,0)),descriptor("db",(0,1)),
        ))
        results=compare((frame,),include_descriptors=True)
        self.assertEqual(len(results),2)
        for result in results:
            self.assertEqual(result.expected_matches,2)
            self.assertEqual(result.correct_matches,2)
            self.assertEqual(result.false_matches,0)
            self.assertEqual(result.missed_matches,0)
        wrong=replace(frame,truth=(("a","db"),("b","da")))
        outcome=evaluate((wrong,),algorithm="geometry")
        self.assertEqual(outcome.correct_matches,0)
        self.assertEqual(outcome.false_matches,2)
        self.assertEqual(outcome.missed_matches,2)

    def test_cv_uses_only_explicit_host_supplied_pixels(self):
        try:
            import cv2
            from PIL import Image
        except ImportError:
            self.skipTest("CV optional extra unavailable")
        image=Image.new("RGB",(16,16),(255,0,0))
        output=BytesIO()
        image.save(output,format="PNG")
        encoded=output.getvalue()
        args=dict(source_id="source",observation_id="frame1",
                  detection_id="det1",frame_index=1,box=(0,0,16,16))
        with self.assertRaises(PermissionError):
            from_frame(encoded,**args)
        descriptor=from_frame(encoded,**args,host_admitted=True)
        self.assertEqual(len(descriptor.vector),128)
        self.assertAlmostEqual(sum(x*x for x in descriptor.vector),1,places=5)
        with self.assertRaises(ValueError):
            from_frame(encoded,**{**args,"box":(0,0,999,999)},host_admitted=True)
        with self.assertRaises(ValueError):
            from_frame(b"not_image",**args,host_admitted=True)


if __name__=="__main__":
    unittest.main()
