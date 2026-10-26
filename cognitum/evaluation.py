"""Synthetic fixture replay only. Never reconstruct grants from traces."""
from .contracts import Request, HostContext, digest

def replay(runtime, cases):
    ids = set()
    rows = []
    for case in cases:
        if set(case) != {"id", "operation", "payload", "expected_status", "expected_result"}:
            raise ValueError("invalid fixture")
        if not isinstance(case["id"], str) or case["id"] in ids:
            raise ValueError("duplicate or invalid case id")
        ids.add(case["id"])
        request = Request(case["id"], "smoke-replay", case["operation"], case["payload"],
                          workspace_id="fixture", subject_id="evaluator")
        result = runtime.call(request, HostContext("fixture", "evaluator", replay=True))
        passed = result.execution_status == case["expected_status"] and result.result == case["expected_result"]
        rows.append({"id": case["id"], "passed": passed, "status": result.execution_status,
                     "result": result.result, "latency_ms": result.latency_ms})
    return {"suite_hash": digest(cases), "registry_hash": digest(runtime.registry.snapshot()),
            "tier": "synthetic_smoke", "promotion_evidence": False,
            "passed": sum(r["passed"] for r in rows), "total": len(rows), "cases": rows}
