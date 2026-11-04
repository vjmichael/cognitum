"""C19 genuine native-library topology-vs-geometry benchmark.

Fixed synthetic shape task only. Produce actual measured heldout classification
scores rather than asserting persistent homology has a universal advantage.
"""
from dataclasses import asdict
import json
from time import perf_counter,process_time
from math import pi,cos,sin
from cognitum.topology_evaluation import benchmark
from cognitum.topology_rips import TopologyQuery,compute,snapshot_hash
from cognitum.topology_gudhi import crosscheck

def run():
    points=tuple((cos(2*pi*i/20),sin(2*pi*i/20)) for i in range(20))
    q=TopologyQuery("reference_ring",snapshot_hash(points),"unitless",
                    "euclidean","vietoris_rips",2.2,1,points)
    start=perf_counter();start_cpu=process_time()
    result=compute(q)
    elapsed=round((perf_counter()-start)*1000,3)
    cpu=round((process_time()-start_cpu)*1000,3)
    if result.status!="OK" or result.longest_finite_h1<.5:
        raise RuntimeError("actual Ripser H1 reference failed")
    independent=crosscheck(q)
    if independent.status!="MATCH":
        raise RuntimeError("actual independent GUDHI comparison failed: "+independent.status)
    start=perf_counter()
    compared=benchmark(ntrain=24,ntest=12)
    benchmark_ms=round((perf_counter()-start)*1000,3)
    if compared.status!="MEASURED_SYNTHETIC_ONLY":
        raise RuntimeError("shape acceptance did not measure actual baselines")
    print(json.dumps({
        "schema_version":1,"benchmark":"C19_actual_Ripser_SciPy_GUDHI_shape",
        "reference":{
            "source_sha256":q.snapshot_sha256,
            "input_points":result.input_points,
            "metric":q.metric,"max_scale":q.maximum_scale,
            "h0_mst_max_deviation":result.h0_mst_max_deviation,
            "longest_h1":result.longest_finite_h1,
            "independent_gudhi":asdict(independent),
            "ripser_wall_ms":elapsed,"ripser_process_cpu_ms":cpu,
        },
        "shape_classification":asdict(compared),
        "total_shape_benchmark_wall_ms":benchmark_ms,
        "limitations":[
            "synthetic_circle_v_disk_not_real_world_scene_or_sensor",
            "no_automatic_topology_advantage_asserted",
            "no_Lu_transformer_with_without_task_benchmark",
            "no_GPU_energy_peak_memory_or_independent_dataset_measured",
            "not_authenticated_data_source_or_canonical_C07_memory",
        ],
    },indent=2,sort_keys=True))
if __name__=="__main__":
    run()
