"""Canonical Python contracts; deliberately small closed schema vocabulary."""
from dataclasses import dataclass, field, asdict
import hashlib
import json
import re
from typing import Protocol

CONTRACT_VERSION = "1.3.0"

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def version(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError("invalid semantic version")
    return tuple(map(int, value.split(".")))

@dataclass(frozen=True)
class Shape:
    """Closed object of bounded strings, not a general JSON Schema interpreter."""
    fields: tuple[tuple[str, int], ...]

    def __post_init__(self):
        if not self.fields or len(dict(self.fields)) != len(self.fields):
            raise ValueError("schema fields must be nonempty and unique")
        if any(not isinstance(k, str) or not k or type(n) is not int or n < 1 for k, n in self.fields):
            raise ValueError("invalid schema field")

    def validate(self, payload):
        if type(payload) is not dict or set(payload) != set(dict(self.fields)):
            raise ValueError("unexpected or missing fields")
        for key, limit in self.fields:
            if type(payload[key]) is not str or not 1 <= len(payload[key]) <= limit:
                raise ValueError("expected bounded nonempty string")

    def json_schema(self):
        return {"type": "object", "additionalProperties": False,
                "required": [k for k, _ in self.fields], "properties": {
                    k: {"type": "string", "minLength": 1, "maxLength": n} for k, n in self.fields}}

@dataclass(frozen=True)
class Effect:
    kind: str
    scope: str

    def __post_init__(self):
        if self.kind not in {"read_state", "write_state", "read_file", "write_file", "network", "execute_code"} or not self.scope:
            raise ValueError("invalid effect")

@dataclass(frozen=True)
class Operation:
    name: str
    slot: str
    input: Shape
    output: Shape
    schema_version: str = "1.0.0"
    effects: tuple[Effect, ...] = ()
    deterministic: bool = True
    assurance: str = "unverified"
    outcome_kind: str = "value"

    def __post_init__(self):
        version(self.schema_version)
        if not self.name or not self.slot:
            raise ValueError("missing operation identity")
        if self.assurance not in {"exact_arithmetic", "numerical", "heuristic", "unverified"}:
            raise ValueError("unsupported assurance")

    def describe(self):
        return {"name": self.name, "slot": self.slot, "schema_version": self.schema_version,
                "input_schema": self.input.json_schema(), "output_schema": self.output.json_schema(),
                "input_hash": digest(self.input.json_schema()), "output_hash": digest(self.output.json_schema()),
                "effects": [asdict(e) for e in self.effects], "deterministic": self.deterministic,
                "assurance": self.assurance, "outcome_kind": self.outcome_kind}

@dataclass(frozen=True)
class Manifest:
    name: str
    version: str
    operations: tuple[Operation, ...]
    contract_version: str = CONTRACT_VERSION
    track: str = "adapter"
    maturity: str = "prototype"

    def __post_init__(self):
        version(self.version)
        # Exact compatibility until a tested migration exists.
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("incompatible contract")
        if not self.name or not self.operations or len({o.name for o in self.operations}) != len(self.operations):
            raise ValueError("invalid manifest")
        if self.track not in {"adapter", "research"} or self.maturity not in {"hypothesis", "prototype"}:
            raise ValueError("Phase 0 cannot promote plugins")

    def describe(self):
        return {"name": self.name, "version": self.version, "contract_version": self.contract_version,
                "track": self.track, "maturity": self.maturity,
                "operations": [o.describe() for o in self.operations]}

@dataclass(frozen=True)
class Request:
    request_id: str
    correlation_id: str
    operation: str
    payload: dict
    workspace_id: str = "local"
    subject_id: str = "local-user"
    contract_version: str = CONTRACT_VERSION
    operation_schema_version: str = "1.0.0"
    timeout_ms: int = 2000
    dry_run: bool = False

    def validate(self):
        for s in (self.request_id, self.correlation_id, self.operation, self.workspace_id, self.subject_id):
            if type(s) is not str or not 1 <= len(s) <= 128:
                raise ValueError("invalid request identity")
        if self.contract_version != CONTRACT_VERSION or type(self.timeout_ms) is not int or not 1 <= self.timeout_ms <= 10000:
            raise ValueError("unsupported contract or timeout")
        if type(self.dry_run) is not bool:
            raise ValueError("invalid dry_run")

@dataclass(frozen=True)
class HostContext:
    """Supplied by trusted host code, never parsed from model payload."""
    workspace_id: str
    subject_id: str
    grants: frozenset[Effect] = frozenset()
    replay: bool = False
    allow_research: bool = False

class Plugin(Protocol):
    def manifest(self) -> Manifest: ...
    def health(self) -> bool: ...
    def self_test(self) -> bool: ...
    def handle(self, operation: str, payload: dict) -> dict: ...

@dataclass
class Response:
    request_id: str
    correlation_id: str
    operation: str
    execution_status: str
    module: dict | None = None
    result: dict | None = None
    outcome: dict | None = None
    assurance: str = "unverified"
    interpretation: dict = field(default_factory=lambda: {"level": "unresolved"})
    evidence: list = field(default_factory=list)
    limitations: list = field(default_factory=list)
    error: str | None = None
    latency_ms: float = 0
    contract_version: str = CONTRACT_VERSION

    def to_dict(self):
        return asdict(self)
