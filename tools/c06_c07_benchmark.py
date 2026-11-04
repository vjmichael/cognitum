"""C06/C07 fixed synthetic reference benchmark, not a Lu-model efficacy claim.

Measures real in-memory SQLite FTS5 retrieval, exact lookup and deterministic
host-owned claim proposal/reconciliation; never user data or canonical writes.
"""
from dataclasses import replace
from time import perf_counter
import json

from cognitum.memory_derived import Evidence,Snapshot,Query,DerivedIndex
from cognitum.belief_proposals import StateEvent,EventSnapshot,propose,current_view

def run():
    docs=tuple(Evidence(
        "source_"+str(i),i+1,"workspace_alpha","document",
        ("reference spacecraft engine " if i%5==0 else "unrelated material ")+str(i),
        "cite_"+str(i),0,None,i%17==0)
        for i in range(500))
    snapshot=Snapshot("Lu_ANSF","owner_revision_501",501,docs)
    start=perf_counter()
    derived=DerivedIndex(snapshot,host_authorized_scope="workspace_alpha")
    built_ms=1000*(perf_counter()-start)
    try:
        start=perf_counter()
        results=derived.query(Query("workspace_alpha","spacecraft engine",
                                    snapshot.snapshot_id,snapshot.owner_revision,
                                    max_results=32))
        query_ms=1000*(perf_counter()-start)
        start=perf_counter()
        exact=derived.exact("workspace_alpha","source_5",
                            expected_owner_revision=501)
        exact_ms=1000*(perf_counter()-start)
        if not results or exact is None or any("unrelated" in x.text for x in results):
            raise RuntimeError("FTS5 synthetic evidence return invalid")
        if any(r.source_id=="source_0" for r in results):
            raise RuntimeError("tombstoned source leaked")
    finally:
        derived.close()
    base=StateEvent("event_1","workspace_alpha","colony","leader",
        "string","Ada","source_1","user_decision",0,0,0,"ASSERT")
    rev=StateEvent("event_2","workspace_alpha","colony","leader",
        "string","Bex","source_2","user_decision",1,1,1,
        "SUPERSEDE","event_1")
    history=EventSnapshot("Lu_ANSF","state_1",1,"workspace_alpha",(base,))
    start=perf_counter()
    p=propose(history,rev,host_authorized_scope="workspace_alpha")
    proposal_ms=1000*(perf_counter()-start)
    if p.status!="HOST_COMMIT_REQUIRED" or len(p.current)!=1 or p.current[0].value!="Bex":
        raise RuntimeError("C07 user revision proposal invalid")
    if current_view(history,host_authorized_scope="workspace_alpha")[0].value!="Ada":
        raise RuntimeError("Cognitum modified canonical source history")
    result={
        "schema":"C06-C07-synthetic-reference-v1",
        "status":"MEASURED_SYNTHETIC",
        "evidence_rows":len(docs),"returned_hits":len(results),
        "fts5_build_ms":round(built_ms,3),
        "fts5_query_ms":round(query_ms,3),
        "exact_lookup_ms":round(exact_ms,3),
        "proposal_reconcile_ms":round(proposal_ms,3),
        "limitations":[
            "synthetic_evidence_not_user_memory",
            "not_an_actual_Lu_ANSF_host_integration",
            "no_cross_chat_model_task_accuracy_measured",
            "single_execution_not_representative_p95_latency",
            "no_Lu_CAS_durable_commit_or_authority_enforcement",
        ],
    }
    print(json.dumps(result,sort_keys=True,indent=2))
    return result

if __name__=="__main__":run()
