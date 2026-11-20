"""MEL-07A CPU routing proposal, not dispatch or authority.

The existing registry remains the sole runtime selection mechanism. No alternate
engine or hardware route is registered here; no device probe implies eligibility.
"""
from dataclasses import dataclass
from . import admission as a, native as n, engines as e
from cognitum.registry import Registry


@dataclass(frozen=True, slots=True)
class CpuSelection:
    operation: str
    backend: str
    descriptor_sha256: str
    plugin: str
    plugin_version: str
    execution_authorized: bool = False


def select_cpu(registry, route, *, preference='auto', allow_research=False):
    """Return a fresh inert CPU proposal, or fail closed.

    CPU is the only reviewed candidate. Explicit GPU/FPGA/distributed requests
    are never silently redirected. Caller must independently grant the exact
    selected operation via Admission, which rechecks the installed entry.
    """
    n.need(type(registry) is Registry and type(route) is a.Route
           and type(allow_research) is bool, 'trusted selection inputs')
    n.need(type(preference) is str and preference in ('auto', 'cpu'),
           'requested backend unavailable or unqualified')
    n.need(allow_research, 'research route not enabled')
    routes = a.routes(include_engines=True)
    n.need(route in routes, 'unsupported or stale route')
    with registry.lock:
        selected = registry.resolve(route.operation, allow_research=True)
        n.need(selected is not None, 'CPU operation unavailable')
        entry, operation = selected
        if route.operation in n.OP:
            n.discover(registry, ((route.public_name, route.descriptor_sha256),))
        else:
            e.discover(registry, ((route.operation, route.descriptor_sha256),))
        n.need(not operation.effects, 'non-computational route')
        return CpuSelection(route.operation, 'cpu', route.descriptor_sha256,
                            entry.manifest.name, entry.manifest.version)
