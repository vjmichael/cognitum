"""C15 deterministic identity reference cases with actual SciPy assignment.

Synthetic checks expose ID switches, missed identities, unassigned detections,
and latency; do not present these as MOT17/TAO/BDD100K measurements.
"""
import json
import platform
from time import perf_counter,process_time
from cognitum.spatial_tracking import Detection,Track,update


def cases():
    initial=(Track("a",0.,0.,8.,8.,last_source="camera_a"),
             Track("b",40.,0.,8.,8.,last_source="camera_a"))
    return (
        ("reordered_detections",initial,
         (Detection("obs_b",40.5,0.,8.,8.,"camera_b"),
          Detection("obs_a",.5,0.,8.,8.,"camera_b")),
         (("a","obs_a"),("b","obs_b"))),
        ("partial_occlusion",initial,
         (Detection("obs_b",40.5,0.,8.,8.,"camera_b"),),
         (("b","obs_b"),)),
        ("distant_rejection",initial,
         (Detection("unrelated",100.,100.,8.,8.,"camera_b"),),()),
    )


def run():
    out=[]
    for name,tracks,detections,expected in cases():
        wall=perf_counter();cpu=process_time()
        result=update(tracks,detections,min_iou=0.05,max_distance=20,max_missed=2)
        wall_ms=round(1000*(perf_counter()-wall),3)
        cpu_ms=round(1000*(process_time()-cpu),3)
        if result.status!="ASSOCIATED":
            raise RuntimeError("missing SciPy native matcher")
        if set(result.assignments)!=set(expected):
            raise RuntimeError("incorrect synthetic matched identity: "+name)
        if len(set(x[0] for x in result.assignments))!=len(result.assignments):
            raise RuntimeError("duplicate stable identity")
        if len(set(x[1] for x in result.assignments))!=len(result.assignments):
            raise RuntimeError("duplicate observation custody")
        out.append({"case":name,"status":result.status,
                    "matches":result.assignments,
                    "unmatched":result.unmatched_detections,
                    "id_switches_vs_fixture":0,
                    "wall_ms":wall_ms,"cpu_ms":cpu_ms})
    print(json.dumps({"schema_version":1,"benchmark":"C15_synthetic_ID_baseline",
        "platform":platform.platform(),"cases":out,
        "limitations":["synthetic_boxes_not_real_sensor_data",
                       "not_MOT17_BDD100K_TAO_or_TrackEval",
                       "not_Lu_model_A_B",
                       "single_run_latency_not_energy_or_memory",
                       "source_strings_not_authenticated"]},indent=2,sort_keys=True))


if __name__=="__main__":
    run()
