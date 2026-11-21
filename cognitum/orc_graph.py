"""ORCH-01A: inert Orc Graph descriptor and plan compiler, not a second executor."""
from dataclasses import dataclass
from types import MappingProxyType

from .cooperative import BRIDGES, Dependency, Plan, SourceStamp, Step, plan_digest
from .cooperative_cpu import ROUTES, parse, type_url

# Source-backed families are not automatically COG-06 admitted operations.
_UNWIRED = MappingProxyType({
    "research.hdc": "cognitum/research/hdc_algebra.py",
    "research.kan": "cognitum/research/kan_trainable.py",
    "research.ssm": "cognitum/research/ssm_timeaware.py",
    "statistical.ridge": "cognitum/research/ssm_timeaware.py",
})
_GOALS = MappingProxyType({
    "exact_linear": ("math.linear",),
    "verified_integer_linear": ("math.linear", "formal.integer"),
})


@dataclass(frozen=True, slots=True)
class Capability:
    operation: str
    input_type_url: str | None
    output_type_url: str | None
    route_sha256: str | None
    assurances: tuple[str, ...]
    eligibility: str
    source_path: str
    units_contract: str = "not_declared"
    clock_contract: str = "not_declared"

    @property
    def execution_authorized(self):
        return False


@dataclass(frozen=True, slots=True)
class ScientificTask:
    goal: str
    frames: tuple[bytes, ...]
    sources: tuple[SourceStamp, ...]

    def __post_init__(self):
        if type(self.goal) is not str or self.goal not in _GOALS:
            raise ValueError("unreviewed scientific goal")
        if type(self.frames) is not tuple or type(self.sources) is not tuple:
            raise ValueError("immutable tuples required")
        if len(self.frames) != len(_GOALS[self.goal]) or len(self.sources) != len(self.frames):
            raise ValueError("incomplete task inputs")
        if any(type(frame) is not bytes for frame in self.frames):
            raise ValueError("immutable protobuf required")
        if any(type(src) is not SourceStamp for src in self.sources):
            raise ValueError("source-stamp contract required")


@dataclass(frozen=True, slots=True)
class Proposal:
    goal: str
    plan: Plan
    route_names: tuple[str, ...]
    plan_sha256: str

    @property
    def execution_authorized(self):
        return False


def catalog() -> tuple[Capability, ...]:
    """All actual reviewed COG-06 CPU routes plus explicitly unwired families."""
    reviewed = tuple(Capability(name, type_url(route.input_class),
                                type_url(route.output_class), route.identity,
                                route.assurances, "existing_host_admission_required",
                                "cognitum/cooperative_cpu.py")
                     for name, route in sorted(ROUTES.items()))
    unwired = tuple(Capability(name, None, None, None, (),
                              "not_wired_or_authorized", path)
                    for name, path in sorted(_UNWIRED.items()))
    return reviewed + unwired


def reviewed_edges() -> tuple[tuple[str, str, str], ...]:
    return tuple((name, src, dst) for name, (src, dst) in sorted(BRIDGES.items()))


def route(task: ScientificTask, *, plan_id: str, workspace_id: str,
          subject_id: str, build_sha: str, timeout_ms: int = 30000,
          step_timeout_ms: int = 10000) -> Proposal:
    """Return the original cooperative Plan; host grants and dispatch stay external."""
    if type(task) is not ScientificTask:
        raise ValueError("typed ScientificTask required")
    names = _GOALS[task.goal]
    for name, frame in zip(names, task.frames):
        parse(frame, ROUTES[name].input_class)
    if task.goal == "verified_integer_linear":
        math = ROUTES["math.linear"].input_class.FromString(task.frames[0])
        formal = ROUTES["formal.integer"].input_class.FromString(task.frames[1])
        if math.action != "solve":
            raise ValueError("integer bridge requires solved exact linear equations")
        if formal.backend != "exhaustive" or formal.proof_required is not True:
            raise ValueError("independent exhaustive integer verification required")
    steps = []
    for i, (name, frame, source) in enumerate(zip(names, task.frames, task.sources)):
        reviewed = ROUTES[name]
        deps = (Dependency("linear", "linear_integer_candidate"),) if i == 1 else ()
        steps.append(Step("linear" if i == 0 else "integer", name,
                          type_url(reviewed.input_class), reviewed.identity,
                          frame, source, step_timeout_ms, deps))
    plan = Plan(plan_id, workspace_id, subject_id, build_sha,
                timeout_ms, tuple(steps))
    return Proposal(task.goal, plan, names, plan_digest(plan))
