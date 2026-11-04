"""C18 actual classical adaptation synthetic future-holdout benchmark.

Contains no raw conversation traces. Reports heldout gains/losses, negative
transfer gates and real CPU/wall timings; not real Lu routing efficacy.
"""
import json
from dataclasses import asdict
from time import perf_counter,process_time

from cognitum.adaptation_policy import (
    Trace,AdaptationProposal,RoutingPolicy,seal,train,score,
)
from cognitum.adaptation_lifecycle import evaluate_promotion
from cognitum.adaptation_retrieval import (
    RetrievalExample,train as train_rank,evaluate as eval_rank,
)

SHA="a"*64

def fixtures():
    base=seal(RoutingPolicy(1,"workspace","tool_router",("general",),2,
        ((0.,0.),(0.,0.),(0.,0.)),(.5,0.,0.),
        (0.,0.),(1.,1.),"b"*64,"base_policy","0"*64,"approved",""))
    p=AdaptationProposal("candidate1","workspace","tool_router",2,SHA,
        "consent_a","public_synthetic",("general",),200000,
        61000,61000,base.digest,80,120000,base.digest)
    labels=("direct","specialist","abstain")
    traces=tuple(Trace("ev_"+str(i),1000*(i+1),
        (float((i%3-1)*3),float(i%3-1)),labels[i%3],SHA,
        "consent_a",200000,"public_synthetic","general") for i in range(90))
    rank=tuple(RetrievalExample(
        "query_"+str(q),"doc_"+str(doc),1000*(q+1),
        (float(4-doc),float(3 if doc==2 else -1)),
        doc==2,SHA,"consent_a")
        for q in range(16) for doc in range(4))
    return base,p,traces,rank

def run():
    base,proposal,rows,ranking=fixtures()
    start=perf_counter();cpu=process_time()
    candidate,holdout=train(proposal,rows,now_ms=100000,host_authorized=True)
    train_wall_ms=round(1000*(perf_counter()-start),3)
    train_cpu_ms=round(1000*(process_time()-cpu),3)
    decision=evaluate_promotion(proposal,candidate,base,holdout)
    start=perf_counter();cpu=process_time()
    learned,rank_holdout=train_rank(ranking,workspace_id="workspace",
             source_digest=SHA,consent_receipt="consent_a",
             cutoff_ms=11000,now_ms=20000,host_authorized=True)
    retrieval_train_ms=round(1000*(perf_counter()-start),3)
    retrieval_cpu_ms=round(1000*(process_time()-cpu),3)
    original=eval_rank(rank_holdout)
    updated=eval_rank(rank_holdout,model=learned)
    if (decision.status!="READY_FOR_HOST_APPROVAL"
            or decision.candidate.accuracy<=decision.incumbent.accuracy
            or updated.mean_reciprocal_rank<=original.mean_reciprocal_rank):
        raise RuntimeError("C18 frozen synthetic candidate did not improve heldout")
    output={
        "schema_version":1,"benchmark":"C18_synthetic_consent_routing_retrieval",
        "router":{
            "candidate_digest":candidate.digest,
            "training_wall_ms":train_wall_ms,
            "training_cpu_ms":train_cpu_ms,
            "future_holdout_count":len(holdout),
            "promotion_gate":decision.status,
            "candidate":asdict(decision.candidate),
            "incumbent":asdict(decision.incumbent),
            "holdout_sha256":decision.holdout_digest,
        },
        "retrieval":{
            "candidate_digest":learned.digest,
            "training_wall_ms":retrieval_train_ms,
            "training_cpu_ms":retrieval_cpu_ms,
            "heldout_queries":len({x.query_id for x in rank_holdout}),
            "baseline":asdict(original),"learned":asdict(updated),
        },
        "limitations":[
            "only_synthetic_numeric_features_and_labels",
            "no_user_private_traces_or_live_Lu_model",
            "heldout_improvement_not_independent_real_task_replication",
            "wall_and_process_CPU_not_peak_memory_or_energy",
            "host_authorized_parameter_is_test_seam_not_host_grant",
            "no_policy_activated_or_Lu_base_transformer_modified",
        ],
    }
    print(json.dumps(output,sort_keys=True,indent=2))

if __name__=="__main__":
    run()
