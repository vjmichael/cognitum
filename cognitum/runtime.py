import json
from time import perf_counter
from .contracts import Request, Response
from .policy import authorize
from .worker import execute, execute_batch, MAX_BATCH
from .tracing import Trace

class Runtime:
    def __init__(self, registry, trace=None, *, warm_pool=None, sandbox_executor=None):
        self.registry = registry
        # The default is the original disposable-worker path. No process is
        # created unless the trusted embedding explicitly provides a pool.
        if warm_pool is not None and sandbox_executor is not None:
            # Only the OS-contained P8 pool tied to this exact P7 executor
            # may coexist with sandbox mode. No P6 multiprocessing bypass.
            from .sandbox_linux import LinuxNamespaceExecutor
            from .sandbox_warm_pool import LinuxSandboxWarmPool
            if (type(sandbox_executor) is not LinuxNamespaceExecutor or
                    type(warm_pool) is not LinuxSandboxWarmPool or
                    warm_pool.executor is not sandbox_executor):
                raise ValueError('WARM_POOL_NOT_CONTAINED_FOR_SANDBOX_RUNTIME')
        self.warm_pool = warm_pool
        self.sandbox_executor = sandbox_executor
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
            if self.sandbox_executor is not None:
                # The sandbox launcher rejects unsupported operations and
                # never silently executes those outside containment.
                frozen = json.loads(json.dumps(request.payload, allow_nan=False))
                operation.input.validate(frozen)
                if (self.warm_pool is not None and
                        self.warm_pool.factory is entry.factory and
                        not operation.effects and operation.deterministic):
                    status, result = self.warm_pool.execute(
                        entry.factory, request.operation, frozen, request.timeout_ms)
                else:
                    status, result = self.sandbox_executor.execute(
                        entry.factory, request.operation, frozen, request.timeout_ms)
            elif (self.warm_pool is not None and self.warm_pool.factory is entry.factory
                    and not operation.effects and operation.deterministic):
                # The request schema and policy have already been checked.
                # Snapshot mutable input before sending it to the standby.
                frozen = json.loads(json.dumps(request.payload, allow_nan=False))
                operation.input.validate(frozen)
                status, result = self.warm_pool.execute(
                    entry.factory, request.operation, frozen, request.timeout_ms)
            else:
                status, result = execute(entry.factory, request.operation, request.payload, request.timeout_ms)
            # Keep the public closed Response/Trace status vocabulary stable.
            # Resource exhaustion is an error with an explicit non-secret code.
            response.execution_status = "completed" if status == "ok" else ("error" if status == "overloaded" else status)
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
                response.error = ("worker_capacity_exhausted" if status == "overloaded"
                                  else None if status == "unavailable" else "plugin_" + status)
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


    def call_batch(self, requests, context, *, trusted_batch_opt_in=False):
        """Optional same-context trusted-plugin optimization, not authority.

        All participants must be deterministic/effect-free, same workspace,
        subject, correlation ID, operation, provider and timeout. Every request
        is validated and authorized BEFORE one disposable worker begins.
        A failed worker or invalid output produces NO partial plugin results.
        This method is deliberately not exposed as a CLI/model/web command.
        """
        if self.sandbox_executor is not None:
            # Existing P6 batch workers are unsandboxed; no bypass.
            raise PermissionError('SANDBOX_BATCH_NOT_IMPLEMENTED')
        if trusted_batch_opt_in is not True:
            raise PermissionError('BATCH_DEFAULT_DISABLED')
        if type(requests) not in (list, tuple) or not 1 <= len(requests) <= MAX_BATCH:
            raise ValueError('INVALID_BATCH_SIZE')
        first = requests[0]
        if type(first) is not Request:
            raise ValueError('INVALID_REQUEST')
        common = (first.correlation_id, first.workspace_id, first.subject_id,
                  first.operation, first.timeout_ms)
        entry = operation = None
        seen_ids = set()
        started = perf_counter()
        pending = []
        for request in requests:
            if type(request) is not Request:
                raise ValueError('INVALID_REQUEST')
            request.validate()
            if (request.correlation_id, request.workspace_id, request.subject_id,
                request.operation, request.timeout_ms) != common:
                raise ValueError('BATCH_CROSSES_CONTEXT_OR_OPERATION')
            if request.request_id in seen_ids:
                raise ValueError('DUPLICATE_BATCH_REQUEST_ID')
            seen_ids.add(request.request_id)
            if request.dry_run:
                raise ValueError('BATCH_DRY_RUN_NOT_EXECUTABLE')
            selected = self.registry.resolve(request.operation, context.allow_research)
            if not selected:
                raise PermissionError('BATCH_CAPABILITY_UNAVAILABLE')
            chosen_entry, chosen_operation = selected
            if operation is None:
                entry, operation = chosen_entry, chosen_operation
            if (chosen_entry.factory is not entry.factory
                or chosen_operation.name != operation.name):
                raise ValueError('BATCH_MIXED_PROVIDER')
            if (chosen_operation.effects or not chosen_operation.deterministic):
                raise PermissionError('BATCH_REQUIRES_PURE_DETERMINISTIC_PLUGIN')
            if request.operation_schema_version != chosen_operation.schema_version:
                raise ValueError('BATCH_SCHEMA_MISMATCH')
            # Freeze and then validate the actual data sent to the child.
            # Never trust a mutable request.payload after it has been checked.
            frozen_payload = dict(request.payload) if type(request.payload) is dict else request.payload
            chosen_operation.input.validate(frozen_payload)
            if len(json.dumps(frozen_payload,allow_nan=False)) > 16384:
                raise ValueError('BATCH_INPUT_TOO_LARGE')
            denial = authorize(request, context, chosen_operation)
            if denial:
                raise PermissionError(denial)
            pending.append((request.operation, frozen_payload))
        assert operation is not None and entry is not None
        try:
            status, results = execute_batch(entry.factory, pending, first.timeout_ms)
        except Exception:
            status, results = 'error', None
        # Validate the ENTIRE set before making any result accessible.
        checked = []
        if status == 'ok' and type(results) is list and len(results) == len(requests):
            try:
                for result in results:
                    operation.output.validate(result)
                    if len(json.dumps(result,allow_nan=False)) > 16384:
                        raise ValueError('oversized output')
                    checked.append(result)
            except (ValueError,TypeError,OverflowError):
                status = 'error'
        else:
            status = 'error' if status not in ('timed_out','invalid_input','error','overloaded') else status
        if status != 'ok':
            checked = []
        responses = []
        for index, request in enumerate(requests):
            response = Response(request.request_id, request.correlation_id, request.operation,
                                'completed' if status == 'ok' else ('error' if status == 'overloaded' else status))
            response.module = {'name':entry.manifest.name,'version':entry.manifest.version}
            if status == 'ok':
                response.result = checked[index]
                response.outcome = {'kind':operation.outcome_kind}
                response.assurance = operation.assurance
                response.interpretation = {'level':'assumption_bound','assumptions':[
                    'The submitted formal input represents the intended task; no natural-language intent validation performed.']}
                response.evidence = [{'kind':'computation','ref':request.request_id}]
            else:
                response.error = ('worker_capacity_exhausted' if status == 'overloaded' else
                                  'invalid_plugin_response_or_worker_failure' if status == 'error'
                                  else 'plugin_'+status)
            responses.append(self._finish(response,started))
        return responses
