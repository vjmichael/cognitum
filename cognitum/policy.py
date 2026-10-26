from .contracts import HostContext, Request, Operation

def authorize(request: Request, context: HostContext, operation: Operation):
    if (request.workspace_id, request.subject_id) != (context.workspace_id, context.subject_id):
        return "identity_scope_mismatch"
    if context.replay and (operation.effects or not operation.deterministic):
        return "replay_requires_inert_deterministic_operation"
    if not set(operation.effects) <= context.grants:
        return "permission_denied"
    # No OS-enforced scoped worker exists yet. Even a grant cannot turn it on.
    if operation.effects:
        return "effectful_execution_not_implemented"
    return None
