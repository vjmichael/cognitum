"""C15 full-design stable identity lifecycle + appearance evidence checks."""
import unittest
from dataclasses import replace
from cognitum.spatial_geometry import Frame,SceneObject
from cognitum.spatial_lifecycle import (
    Evidence,Entity,SceneRevision,SceneMutation,validate_revision,resolve,mutate,
)
from cognitum.spatial_tracking import Track,Detection
from cognitum.spatial_appearance_core import Appearance,associate_appearance,validate_descriptors

DIGEST="a"*64
def evidence(name="event",at=10,kind="manual_annotation"):
    return Evidence("camera_a",name,at,0.8,"world",kind,"approved_source",DIGEST)

def revision():
    obj=SceneObject("object_one","world",(0.,0.,0.),(1.,1.,1.),
                    True,"camera_a",10,1)
    return SceneRevision("scene1",0,(),(Entity(obj,(),(evidence(),),"visible"),),
                         100,())

def appearance(name,values,frame=1,encoder="model_a"):
    return Appearance(name,tuple(values),encoder,DIGEST,"source_a",
                      "obs_"+name,frame)


class C15LifecycleTests(unittest.TestCase):
    def test_rename_visibility_deletion_and_version_monotonicity(self):
        s=revision()
        rename=SceneMutation("mut1","object_one","rename",1,alias="new_alias",
                             evidence=evidence("rename"))
        with self.assertRaises(ValueError):
            mutate(s,rename,expected_revision=0)
        s=mutate(s,rename,expected_revision=0,admitted_by_trusted_host=True)
        self.assertEqual(s.revision,1)
        self.assertEqual(resolve(s,"new_alias").obj.stable_id,"object_one")
        self.assertEqual(resolve(s,"object_one").obj.version,2)
        with self.assertRaises(ValueError):
            mutate(s,rename,expected_revision=1,admitted_by_trusted_host=True)
        with self.assertRaises(ValueError):
            mutate(s,SceneMutation("mut2","object_one","occlude",1,evidence=evidence("occlusion")),
                   expected_revision=1,admitted_by_trusted_host=True)
        s=mutate(s,SceneMutation("mut2","object_one","occlude",2,evidence=evidence("occlusion")),
                 expected_revision=1,admitted_by_trusted_host=True)
        self.assertEqual(s.entities[0].state,"occluded")
        self.assertEqual(s.entities[0].obj.stable_id,"object_one")
        s=mutate(s,SceneMutation("mut3","object_one","reveal",3,evidence=evidence("reappearance")),
                 expected_revision=2,admitted_by_trusted_host=True)
        self.assertEqual(s.entities[0].state,"visible")
        s=mutate(s,SceneMutation("mut4","object_one","delete",4,evidence=evidence("deletion")),
                 expected_revision=3,admitted_by_trusted_host=True)
        self.assertEqual(s.entities[0].state,"deleted")
        with self.assertRaises(ValueError):
            resolve(s,"new_alias")
        with self.assertRaises(ValueError):
            mutate(s,SceneMutation("mut5","object_one","reveal",5,evidence=evidence("again")),
                   expected_revision=4,admitted_by_trusted_host=True)
        self.assertEqual(resolve(s,"object_one",include_deleted=True).obj.version,5)

    def test_conflicting_alias_and_unauthenticated_source_rejected(self):
        s=revision()
        other=SceneObject("other_object","world",(1.,0.,0.),(1.,1.,1.),
                          True,"camera_a",10,1)
        s=mutate(s,SceneMutation("create2","other_object","create",0,
                  object_value=other,evidence=evidence("other")),
                 expected_revision=0,admitted_by_trusted_host=True)
        s=mutate(s,SceneMutation("rename1","object_one","rename",1,alias="shared",
                  evidence=evidence("alias1")),
                 expected_revision=1,admitted_by_trusted_host=True)
        with self.assertRaises(ValueError):
            mutate(s,SceneMutation("rename2","other_object","rename",1,alias="shared",
                    evidence=evidence("alias2")),
                   expected_revision=2,admitted_by_trusted_host=True)
        invalid=replace(s.entities[0],evidence=(replace(evidence(),confidence=float("nan")),))
        with self.assertRaises(ValueError):
            validate_revision(replace(s,entities=(invalid,)+s.entities[1:]))

    def test_no_edit_without_host_admission(self):
        s=revision()
        m=SceneMutation("mut9","object_one","delete",1,evidence=evidence("request"))
        for approval in (False,0,None):
            with self.assertRaises(ValueError):
                mutate(s,m,expected_revision=0,admitted_by_trusted_host=approval)


class C15AppearanceTests(unittest.TestCase):
    def test_reidentification_with_appearance(self):
        t=(Track("a",0,0,10,10),Track("b",15,0,10,10))
        d=(Detection("da",8,0,10,10,"camera"),Detection("db",9,0,10,10,"camera"))
        descriptors=(appearance("a",(1,0,0)),appearance("b",(0,1,0)),
                     appearance("da",(1,0,0)),appearance("db",(0,1,0)))
        out=associate_appearance(t,d,descriptors)
        self.assertEqual(out.status,"ASSOCIATED")
        self.assertEqual(out.matches,(("a","da"),("b","db")))
        self.assertEqual(out.unmatched_detections,())

    def test_ambiguous_appearance_abstains(self):
        tracks=(Track("a",0,0,10,10),)
        dets=(Detection("d1",0,0,10,10,"camera"),
              Detection("d2",0,0,10,10,"camera"))
        descriptors=(appearance("a",(1,0)),
                     appearance("d1",(1,0)),appearance("d2",(1,0)))
        out=associate_appearance(tracks,dets,descriptors)
        self.assertEqual(out.status,"AMBIGUOUS")
        self.assertEqual(out.matches,())
        self.assertEqual(out.ambiguous_tracks,("a",))
        self.assertEqual(set(out.unmatched_detections),{"d1","d2"})

    def test_no_automatic_coercion_of_incompatible_encoders(self):
        t=(Track("a",0,0,5,5),)
        d=(Detection("d1",0,0,5,5,"camera"),)
        for descriptors in (
            (appearance("a",(1,0)),appearance("d1",(1,0),encoder="other")),
            (appearance("a",(1,0)),appearance("d1",(1,0,0))),
            (appearance("a",(0,0)),appearance("d1",(1,0))),
            (appearance("a",(1,0)),appearance("a",(1,0))),
        ):
            with self.subTest(descriptors=repr(descriptors)[:100]),self.assertRaises(ValueError):
                validate_descriptors(t,d,descriptors)


if __name__=="__main__":
    unittest.main()
