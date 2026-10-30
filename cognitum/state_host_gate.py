"""C07/P2 host-lease *reference contract* for admitting and publishing beliefs.

There is no credential, principal constructor, or trust decision in this Python
module. A Lu-native host must acquire an authenticated, scope-bound lease and
implement all three methods using trusted conversation/ANSF records. An object
provided by a model, document, external plugin or webview is NEVER a lease.

Call the ledger's ``apply_host_batch`` / ``publish_host_fenced`` *within* an
already-held host read/mutation lease. The host owns the lifetime and the
callback is invoked before release, so it can synchronize revocation/deletion
with disclosure. This is only a synthetic contract until Lu Rust is integrated.
"""
from __future__ import annotations

from typing import Protocol

from cognitum.proto import state_pb2 as pb


class SourceUnavailable(ValueError):
    """A host check failed. Does not expose which source or grant was denied."""


class HostStateLease(Protocol):
    def ensure_active(self) -> bool:
        """Return exactly True if the authenticated host lease is still valid."""

    def admit_event(self, scope_id: str, event: pb.StateEvent) -> bool:
        """Verify host event origin, writer action, source ownership and scope."""

    def verify_source(self, scope_id: str, source: pb.SourceEvidence,
                      require_current: bool) -> bool:
        """Check retained historical source vs latest-current, with deletion.

        For both paths, host must recheck owner/scope and content hash. For
        require_current=True it must ALSO match the canonical revision head.
        Historical evidence must never become a new current claim merely
        because the bytes still exist on disk.
        """


class HostDeletionLease(HostStateLease, Protocol):
    def confirm_source_deleted(self, scope_id: str, source: pb.SourceEvidence) -> bool:
        """Host-confirmed permanent logical source tombstone under the held delete lease.

        A candidate source list supplied to the journal is NEVER proof of deletion.
        This separate permission must come from Lu's authenticated deletion authority.
        """


def require_host_pass(fn, *args) -> None:
    """Fail closed; never publish exception messages, source IDs or partial data."""
    try:
        verdict = fn(*args)
    except Exception:
        raise SourceUnavailable('host evidence unavailable') from None
    if verdict is not True:
        raise SourceUnavailable('host evidence unavailable')
