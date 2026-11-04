"""C15 cross-source conflict, workspace detachment and durable isolation."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitum.spatial_geometry import SceneObject,Frame
from cognitum.spatial_lifecycle import (
    Entity,Evidence,SceneRevision,SceneMutation,mutate,resolve,
    validate_revision,detach_workspace,
)
from cognitum.spatial_observation_consistency import (
    MetricObservation,compare_observations,
)
from cognitum.spatial_scene_journal import SceneJournal

DIGEST="b"*64

def source_event(obs):
    return Evidence("camera",obs,1,.8,"world","sensor_detection","host_record",DIGEST)

def scene(workspace):
    obj=SceneObject("person","world",(0.,0.,0.),(.5,.5,1.8),
                    True,"camera",1,1)
    return SceneRevision("scene1",0,(),(Entity(obj,(),(source_event("first"),),"visible"),),
                         2,(),workspace)

def observation(name,source,point,frame="world"):
    return MetricObservation(name,"subject",source,frame,point,.1,5,"host_admit")


class C15ScopeAndConsistency(unittest.TestCase):
    def test_independent_workspaces_survive_same_scene_id(self):
        with TemporaryDirectory() as root:
            db=SceneJournal(Path(root)/"state.sqlite")
            one=scene("workspace_a")
            two=scene("workspace_b")
            db.put(one,expected_previous=-1)
            db.put(two,expected_previous=-1)
            self.assertEqual(db.restore("scene1",workspace_id="workspace_a"),one)
            self.assertEqual(db.restore("scene1",workspace_id="workspace_b"),two)
            self.assertIsNone(db.restore("scene1",workspace_id="workspace_c"))
            db.close()

    def test_detach_blocks_mutation_and_identity_query(self):
        first=scene("workspace_a")
        with self.assertRaises(ValueError):
            detach_workspace(first,expected_revision=0,event_id="detach1")
        detached=detach_workspace(first,expected_revision=0,event_id="detach1",
                                  admitted_by_trusted_host=True)
        self.assertTrue(detached.detached)
        self.assertEqual(detached.revision,1)
        with self.assertRaises(ValueError):
            resolve(detached,"person")
        with self.assertRaises(ValueError):
            mutate(detached,SceneMutation("next","person","occlude",1,
                                         evidence=source_event("occlusion")),
                   expected_revision=1,admitted_by_trusted_host=True)
        with TemporaryDirectory() as root:
            db=SceneJournal(Path(root)/"state.sqlite")
            db.put(first,expected_previous=-1)
            db.put(detached,expected_previous=0)
            db.close()
            db=SceneJournal(Path(root)/"state.sqlite")
            self.assertTrue(db.restore("scene1",workspace_id="workspace_a").detached)
            db.close()

    def test_cross_camera_agreement_and_conflict(self):
        f=(Frame("camera_a","world",(0.,0.,0.),(0.,0.,0.,1.)),
           Frame("camera_b","world",(1.,0.,0.),(0.,0.,0.,1.)))
        a=observation("obsa","sensor_a",(1.,0.,0.),"camera_a")
        b=observation("obsb","sensor_b",(0.,0.,0.),"camera_b")
        coherent=compare_observations(f,a,b,epoch=5)
        self.assertEqual(coherent.status,"CONSISTENT")
        self.assertAlmostEqual(coherent.separation_m,0)
        contradictory=compare_observations(f,a,replace(b,point_m=(10.,0.,0.)),
                                            epoch=5)
        self.assertEqual(contradictory.status,"CONFLICT")
        self.assertGreater(contradictory.normalized_separation,3)

    def test_reject_duplicate_source_and_unverified_time(self):
        a=observation("a","source_a",(0.,0.,0.))
        for bad in (
            replace(a,observation_id="a"),
            replace(a,observation_id="b",observed_at_ms=6),
            replace(a,observation_id="b",sigma_m=-1),
            replace(a,observation_id="b",stable_id="other"),
        ):
            with self.subTest(bad=repr(bad)),self.assertRaises(ValueError):
                compare_observations((),a,bad,epoch=5)
        with self.assertRaises(ValueError):
            compare_observations((),a,
                replace(a,observation_id="b",source_id="source_a"),epoch=5)


if __name__=="__main__":
    unittest.main()
