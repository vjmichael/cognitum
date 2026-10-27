"""C02 offline Protobuf supervisor acceptance SPECIFICATION, not a sandbox.

The plan enumerates what Lu's future trusted OS supervisor must prove on
Windows/Linux/macOS. It cannot attest that any actual restrictions were
applied. A matching message from a worker is NEVER authentication or proof.
The simulated lifecycle checker only tests state-transition expectations.
Worker admission remains unconditionally denied by worker_wire.py.
"""
from dataclasses import dataclass

from google.protobuf.message import DecodeError

from .proto import supervisor_acceptance_pb2 as pb

ACCEPTANCE_TYPE_URL = "type.googleapis.com/cognitum.security.v1.SupervisorAcceptancePlan"
WORKER_WIRE_TYPE = "type.googleapis.com/cognitum.worker.v1.WorkerCall"
MAX_PLAN_BYTES = 16 * 1024
_VERSION = 1
# (probe ID, kind, platform, expected, checked host-side negative condition)
_PROBES = (
    ("deny-missing-grant", pb.HOST_IDENTITY_AND_GRANTS, pb.PLATFORM_ALL, pb.EXPECT_DENY,
     "No worker starts without a Lu-authenticated principal, task and exact scope grant"),
    ("deny-model-grant", pb.MODEL_FORGED_AUTHORITY, pb.PLATFORM_ALL, pb.EXPECT_DENY,
     "A model-produced token, instruction or claimed approval does not grant authority"),
    ("deny-replay", pb.REPLAYED_OR_STALE_CALL, pb.PLATFORM_ALL, pb.EXPECT_DENY,
     "Replayed, expired, cross-profile and cross-session calls fail closed"),
    ("deny-tool-effect", pb.UNREGISTERED_TOOL_OR_EFFECT, pb.PLATFORM_ALL, pb.EXPECT_DENY,
     "Unknown tools and missing or mismatched effect declarations never execute"),
    ("deny-sandbox-unavailable", pb.SANDBOX_UNAVAILABLE, pb.PLATFORM_ALL, pb.EXPECT_DENY,
     "Absent, unsupported or failed OS isolation never silently falls back to spawn"),
    ("windows-private-read", pb.PRIVATE_FILE_READ, pb.PLATFORM_WINDOWS, pb.EXPECT_DENY,
     "Restricted Windows worker cannot read private profile files or credentials"),
    ("linux-private-read", pb.PRIVATE_FILE_READ, pb.PLATFORM_LINUX, pb.EXPECT_DENY,
     "Restricted Linux worker cannot read private profile files or credentials"),
    ("macos-private-read", pb.PRIVATE_FILE_READ, pb.PLATFORM_MACOS, pb.EXPECT_DENY,
     "Restricted macOS worker cannot read private profile files or credentials"),
    ("windows-write", pb.OUT_OF_SCOPE_WRITE, pb.PLATFORM_WINDOWS, pb.EXPECT_DENY,
     "Windows worker cannot write outside broker-approved paths or via reparse points"),
    ("linux-write", pb.OUT_OF_SCOPE_WRITE, pb.PLATFORM_LINUX, pb.EXPECT_DENY,
     "Linux worker cannot write outside broker-approved paths or symlinks"),
    ("macos-write", pb.OUT_OF_SCOPE_WRITE, pb.PLATFORM_MACOS, pb.EXPECT_DENY,
     "macOS worker cannot write outside broker-approved paths or symlinks"),
    ("windows-network", pb.NETWORK_DNS_LOOPBACK, pb.PLATFORM_WINDOWS, pb.EXPECT_DENY,
     "Windows worker cannot access DNS, loopback or external networks by default"),
    ("linux-network", pb.NETWORK_DNS_LOOPBACK, pb.PLATFORM_LINUX, pb.EXPECT_DENY,
     "Linux worker cannot access DNS, loopback or external networks by default"),
    ("macos-network", pb.NETWORK_DNS_LOOPBACK, pb.PLATFORM_MACOS, pb.EXPECT_DENY,
     "macOS worker cannot access DNS, loopback or external networks by default"),
    ("windows-handles", pb.SENSITIVE_HANDLE_INHERITANCE, pb.PLATFORM_WINDOWS, pb.EXPECT_DENY,
     "Windows process and token handle inheritance cannot leak secrets or authority"),
    ("linux-handles", pb.SENSITIVE_HANDLE_INHERITANCE, pb.PLATFORM_LINUX, pb.EXPECT_DENY,
     "Linux inherited file descriptors and environment cannot leak secrets"),
    ("macos-handles", pb.SENSITIVE_HANDLE_INHERITANCE, pb.PLATFORM_MACOS, pb.EXPECT_DENY,
     "macOS inherited descriptors and environment cannot leak secrets"),
    ("windows-descendants", pb.PROCESS_TREE_BREAKAWAY, pb.PLATFORM_WINDOWS,
     pb.EXPECT_KILL_AND_REAP, "Windows Job Object kills worker descendants and prevents breakaway"),
    ("linux-descendants", pb.PROCESS_TREE_BREAKAWAY, pb.PLATFORM_LINUX,
     pb.EXPECT_KILL_AND_REAP, "Linux supervisor kills worker process group/cgroup descendants"),
    ("macos-descendants", pb.PROCESS_TREE_BREAKAWAY, pb.PLATFORM_MACOS,
     pb.EXPECT_KILL_AND_REAP, "macOS supervisor kills worker descendants and prevents orphans"),
    ("windows-limits", pb.RESOURCE_LIMITS, pb.PLATFORM_WINDOWS,
     pb.EXPECT_RESOURCE_ENFORCEMENT, "Windows enforces CPU, RAM, process and wall-time quotas"),
    ("linux-limits", pb.RESOURCE_LIMITS, pb.PLATFORM_LINUX,
     pb.EXPECT_RESOURCE_ENFORCEMENT, "Linux enforces CPU, RAM, process and wall-time quotas"),
    ("macos-limits", pb.RESOURCE_LIMITS, pb.PLATFORM_MACOS,
     pb.EXPECT_RESOURCE_ENFORCEMENT, "macOS enforces CPU, RAM, process and wall-time quotas"),
    ("timeout-cancel", pb.TIMEOUT_AND_CANCEL, pb.PLATFORM_ALL,
     pb.EXPECT_KILL_AND_REAP, "Timeout or cancellation stops new calls and reaps all descendants"),
    ("revoke-running", pb.REVOKE_DURING_CALL, pb.PLATFORM_ALL,
     pb.EXPECT_KILL_AND_REAP, "Grant revocation cancels active calls and drains/reaps workers"),
    ("workspace-unload", pb.WORKSPACE_CE_UNLOAD, pb.PLATFORM_ALL,
     pb.EXPECT_PRESERVE_UNRELATED, "CE unload drains own workers without breaking Lu or other DLCs"),
    ("reject-late-reply", pb.LATE_REPLY_AFTER_REVOKE, pb.PLATFORM_ALL,
     pb.EXPECT_REJECT_LATE_RESULT, "Worker results arriving after revocation are discarded"),
    ("audit-no-secrets", pb.AUDIT_SECRET_LEAKAGE, pb.PLATFORM_ALL,
     pb.EXPECT_METADATA_ONLY, "Only approved nonsecret metadata can enter audit records"),
)


def acceptance_plan():
    """Create a frozen NEGATIVE test specification, never a passed security report."""
    plan = pb.SupervisorAcceptancePlan(
        schema_version=_VERSION,
        ce_id="cognitum.calc",
        worker_wire_type=WORKER_WIRE_TYPE,
        production_launch_enabled=False,
    )
    for id_, kind, platform, expected, description in _PROBES:
        plan.probes.add(
            id=id_, kind=kind, platform=platform, expected=expected,
            description=description,
        )
    if len(plan.SerializeToString(deterministic=True)) > MAX_PLAN_BYTES:
        raise ValueError("supervisor test specification exceeded bound")
    return plan


def encode_acceptance_plan():
    return acceptance_plan().SerializeToString(deterministic=True)


def decode_acceptance_plan(frame):
    if type(frame) is not bytes or not 0 < len(frame) <= MAX_PLAN_BYTES:
        raise ValueError("invalid acceptance plan frame")
    plan = pb.SupervisorAcceptancePlan()
    try:
        plan.ParseFromString(frame)
    except DecodeError as error:
        raise ValueError("malformed acceptance plan Protobuf") from error
    known = pb.SupervisorAcceptancePlan()
    known.CopyFrom(plan)
    known.DiscardUnknownFields()
    if known != plan or plan.SerializeToString(deterministic=True) != frame:
        raise ValueError("unknown or noncanonical acceptance plan fields")
    if plan != acceptance_plan():
        raise ValueError("unreviewed acceptance scenario or authority claim")
    return plan


@dataclass(frozen=True)
class OfflineLifecycleCheck:
    """A model check, explicitly not OS test evidence or permission."""
    sequence_valid: bool
    os_confinement_verified: bool = False
    launch_permitted: bool = False


def check_synthetic_shutdown(events: tuple[str, ...]):
    """Check a SPECULATIVE host lifecycle event sequence, without launching.

    The only recognized successful path is request stop -> block new calls ->
    terminate and reap descendants -> discard a late worker result. A fake
    event stream cannot make os_confinement_verified or launch_permitted True.
    """
    if type(events) is not tuple or len(events) != 7 or any(type(e) is not str for e in events):
        raise ValueError("bounded synthetic host event tuple required")
    if events[0:2] != ("synthetic_admission", "synthetic_worker_started"):
        raise ValueError("unknown synthetic admission lifecycle")
    if events[2] not in ("cancel_requested", "grant_revoked", "ce_unloaded", "timed_out"):
        raise ValueError("missing supervisor stop trigger")
    if events[3:] != (
        "new_call_denied", "descendant_tree_terminated",
        "descendant_tree_reaped", "late_reply_rejected",
    ):
        raise ValueError("unsafe shutdown, orphan or acceptance of late result")
    return OfflineLifecycleCheck(sequence_valid=True)
