import json
from time import perf_counter
from .contracts import Request, Response
from .policy import authorize
from .worker import execute
from .tracing import Trace

class Runtime:
    def __init__(self, registry, trace=None):
        self.registry = registry
        self.trace = trace if trace is not None else Trace()

    def call(self, request: Request, context):
        start = perf_counter()
        response = Response(request.request_id, request.correlation_id, request.operation, "invalid_input")
        try:
            request.validate()
        except (ValueError, TypeError):
            response.error = "invalid_request"
            return self._finish(response, start)
        selected = self.registry.resolve(request.operation, context.allow_research)
        if not selected:
            response.execution_status = "unavailable"
            response.limitations = ["Capability unavailable; no computed or verified answer supplied."]
            return self._finish(response, start)
        entry, operation = selected
        response.module = {"name": entry.manifest.name, "version": entry.manifest.version}
        try:
            if request.operation_schema_version != operation.schema_version:
                raise ValueError("schema version mismatch")
            operation.input.validate(request.payload)
        except (ValueError, TypeError):
            response.error = "invalid_operation_input"
            return self._finish(response, start)
        denial = authorize(request, context, operation)
        if denial:
            response.execution_status = "denied"
            response.error = denial
            return self._finish(response, start)
        if request.dry_run:
            response.execution_status = "validated"
            response.limitations = ["Schema and policy checked only; plugin not executed."]
            return self._finish(response, start)
        try:
            status, result = execute(entry.factory, request.operation, request.payload, request.timeout_ms)
            response.execution_status = status if status != "ok" else "completed"
            if status == "ok":
                operation.output.validate(result)
                if len(json.dumps(result)) > 16384:
                    raise ValueError("oversized output")
                response.result = result
                response.outcome = {"kind": operation.outcome_kind}
                response.assurance = operation.assurance
                response.interpretation = {"level": "assumption_bound", "assumptions": [
                    "The submitted formal input represents the intended task; no natural-language intent validation performed."]}
                response.evidence = [{"kind": "computation", "ref": request.request_id}]
            else:
                response.error = "plugin_" + status
        except Exception:
            response.execution_status = "error"
            response.error = "invalid_plugin_response_or_worker_failure"
            response.result = None
        return self._finish(response, start)

    def _finish(self, response, start):
        if response.execution_status not in {"completed", "validated"} and not response.limitations:
            response.limitations = ["No computed or verified answer supplied."]
        response.latency_ms = round((perf_counter() - start) * 1000, 3)
        self.trace.append({"trace_version": "1.0.0", "request_id": response.request_id,
                           "correlation_id": response.correlation_id, "operation": response.operation,
                           "module": response.module, "execution_status": response.execution_status,
                           "error": response.error, "latency_ms": response.latency_ms})
        return response
