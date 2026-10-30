"""C06/P2 offline reference boundary for host-fenced retrieval and citations.

This module is NOT a Lu adapter or authorization provider. The injected host
owns authenticated identity, session grants, source bytes, revocation locks,
snapshot epochs and the delivery channel. Model-facing and external callers
must never select their own lease/snapshot or use fixture-backed gateways in
production. No disk access, ANSF queries or CE/tool registration is performed.

Critical lifetime guarantee: host.publish() is called *while its read lease is
held*, after a fresh host.recheck() and before releasing the lease. A caller
cannot take the returned DeliveryReceipt as proof of authorization: it carries
no evidence bytes. An implementation where publish() queues output for later
unfenced delivery does NOT satisfy the contract.
"""
from dataclasses import dataclass
import hmac
import re
from typing import ContextManager, Protocol, runtime_checkable

from .memory_evidence import (
    _context_valid, _id, _source, _strict_decode, encode_frame,
    verify_candidate_batch, SCHEMA_VERSION, MAX_EXCERPT_BYTES,
    MAX_CANONICAL_BYTES, QUERY_FRAME_LIMIT,
)
from .proto import memory_pb2 as pb
from .memory_literal import select_literal_candidates

CITATION_FRAME_LIMIT = 4096
# Handles are public locators, not tokens or credentials.
_HANDLE = re.compile(r"ref_[0-9a-f]{64}\Z", re.ASCII)


@runtime_checkable
class HostHeldRead(Protocol):
    """Accessible only inside host's synchronized, authenticated read lease.

    The host MUST hold the authorization/revision/deletion fence across the
    entire lease, including synchronous publish. recheck() MUST reflect a
    fresh host-owned source/grant state; it must never trust model attributes.
    """
    @property
    def context(self): ...

    @property
    def snapshot_frame(self) -> bytes: ...

    def recheck(self) -> int: ...

    def publish(self, reply_frame: bytes) -> None: ...


@runtime_checkable
class HostMemoryGateway(Protocol):
    def acquire(self) -> ContextManager[HostHeldRead]: ...


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    """Only bookkeeping: no source text, no authority, no model-visible tool."""
    status: int
    published: bool


def _lookup_reply(request_id, status, evidence=None):
    reply = pb.CitationResolution(schema_version=SCHEMA_VERSION,
                                  request_id=request_id if _id(request_id) and len(request_id) <= 64 else "",
                                  status=status)
    if evidence is not None:
        reply.evidence.CopyFrom(evidence)
    return reply


def _empty_reply(operation, frame, status):
    """Keep failures closed and never publish a partial evidence result."""
    request_id = ""
    try:
        kind = pb.MemoryQuery if operation in ("search", "literal", "ansf_fts") else pb.CitationLookup
        parsed = _strict_decode(frame, kind, QUERY_FRAME_LIMIT if operation in ("search", "literal", "ansf_fts") else CITATION_FRAME_LIMIT)
        request_id = parsed.request_id
    except ValueError:
        pass
    if operation in ("search", "literal", "ansf_fts"):
        return pb.RetrievalReply(schema_version=SCHEMA_VERSION,
                                 request_id=request_id if _id(request_id) and len(request_id) <= 64 else "",
                                 status=status)
    return _lookup_reply(request_id, status)


def verify_citation_lookup(lookup_frame, snapshot_frame, *, context):
    """Revalidate a citation through P1's canonical source verifier.

    All fields on the lookup are treated as hostile hints. The host must
    independently authorize, fence, and supply the current snapshot before
    calling this helper. Citation handles are not unforgeable capabilities.
    """
    empty = pb.CitationResolution(schema_version=SCHEMA_VERSION, status=pb.INVALID)
    if not _context_valid(context) or not context.active:
        empty.status = pb.DENIED
        return empty
    if type(lookup_frame) is bytes and len(lookup_frame) > CITATION_FRAME_LIMIT:
        empty.status = pb.LIMIT
        return empty
    try:
        lookup = _strict_decode(lookup_frame, pb.CitationLookup, CITATION_FRAME_LIMIT)
    except ValueError:
        return empty
    if lookup.schema_version != SCHEMA_VERSION:
        return _lookup_reply(lookup.request_id, pb.UNSUPPORTED)
    if not (_id(lookup.request_id) and len(lookup.request_id) <= 64 and
            _HANDLE.fullmatch(lookup.citation_handle) and _source(lookup.source) and
            _id(lookup.snapshot_id) and re.fullmatch(r"[0-9a-f]{64}", lookup.content_sha256) and
            1 <= lookup.length_utf8_byte <= MAX_EXCERPT_BYTES and
            lookup.start_utf8_byte <= MAX_CANONICAL_BYTES):
        return _lookup_reply(lookup.request_id, pb.INVALID)
    query = pb.MemoryQuery(schema_version=SCHEMA_VERSION, request_id=lookup.request_id,
                           literal_query="citation", max_results=1,
                           include_historical=context.allow_historical)
    query.exact_sources.add().CopyFrom(lookup.source)
    batch = pb.CandidateBatch(schema_version=SCHEMA_VERSION)
    candidate = batch.candidates.add()
    candidate.source.CopyFrom(lookup.source)
    candidate.content_sha256 = lookup.content_sha256
    candidate.snapshot_id = lookup.snapshot_id
    candidate.scope_id = context.scope_id  # host-supplied, NOT caller-selected
    candidate.start_utf8_byte = lookup.start_utf8_byte
    candidate.length_utf8_byte = lookup.length_utf8_byte
    answer = verify_candidate_batch(encode_frame(query), encode_frame(batch),
                                    snapshot_frame, context=context)
    if answer.status != pb.VERIFIED or len(answer.evidence) != 1:
        return _lookup_reply(lookup.request_id, answer.status)
    evidence = answer.evidence[0]
    if not hmac.compare_digest(lookup.citation_handle, evidence.citation_handle):
        return _lookup_reply(lookup.request_id, pb.STALE)
    return _lookup_reply(lookup.request_id, pb.VERIFIED, evidence)


def dispatch_host_fenced(operation, request_frame, *, gateway, candidate_frame=None):
    """Publish ONLY inside a host-owned lease; receipt contains no evidence.

    ``operation``: 'search', 'literal' (synthetic linear comparator),
    'ansf_fts' (host-owned ANSF search fixture), 'citation',
    or 'ansf_citation' (host-owned ANSF citation fixture). The original
    search operation requires untrusted ``candidate_frame``; literal derives
    candidates from a host-injected snapshot; ANSF operations require
    host-held reader methods; citations use native CitationLookup requests.

    Gateway must be supplied exclusively by authenticated Lu host code; the
    protocol and Python object shape cannot authenticate an arbitrary gateway.
    Returns no evidence even on success. A host must not deliver asynchronously
    after lease release. Failures in acquiring/rechecking/publishing the lease
    are suppressed to UNAVAILABLE in the receipt; no response is published.
    """
    if operation not in ("search", "literal", "ansf_fts", "citation", "ansf_citation"):
        raise ValueError("unsupported memory operation")
    if not isinstance(request_frame, bytes):
        # In particular never coerce arbitrary objects into source frames.
        return DeliveryReceipt(pb.INVALID, False)
    try:
        with gateway.acquire() as lease:
            if not _context_valid(lease.context) or not lease.context.active:
                reply = _empty_reply(operation, request_frame, pb.DENIED)
            elif operation in ("search", "literal", "ansf_fts"):
                if operation == "ansf_fts":
                    if candidate_frame is not None:
                        reply = _empty_reply(operation, request_frame, pb.INVALID)
                    else:
                        # Only a HOST-held read lease may fetch ANSF bytes. The
                        # gateway object alone does not authenticate callers.
                        status, hits, canonical = lease.ansf_fts_frames(request_frame)
                        reply = (verify_candidate_batch(request_frame, hits, canonical,
                                                       context=lease.context)
                                 if status == pb.VERIFIED else
                                 _empty_reply(operation, request_frame, status))
                elif operation == "literal":
                    if candidate_frame is not None:
                        reply = _empty_reply(operation, request_frame, pb.INVALID)
                    else:
                        status, candidate_frame = select_literal_candidates(
                            request_frame, lease.snapshot_frame, context=lease.context)
                        reply = (verify_candidate_batch(request_frame, candidate_frame,
                                                       lease.snapshot_frame, context=lease.context)
                                 if status == pb.VERIFIED else
                                 _empty_reply(operation, request_frame, status))
                else:
                    reply = verify_candidate_batch(request_frame, candidate_frame,
                                                   lease.snapshot_frame, context=lease.context)
            elif operation == "ansf_citation":
                if candidate_frame is not None:
                    reply = _empty_reply(operation, request_frame, pb.INVALID)
                else:
                    status, canonical = lease.ansf_citation_snapshot(request_frame)
                    reply = (verify_citation_lookup(request_frame, canonical,
                                                    context=lease.context)
                             if status == pb.VERIFIED else
                             _empty_reply(operation, request_frame, status))
            else:
                reply = verify_citation_lookup(request_frame, lease.snapshot_frame,
                                               context=lease.context)
            # Last pre-delivery check is host-owned, never supplied by candidate.
            status = lease.recheck()
            if type(status) is not int or status not in (
                    pb.VERIFIED, pb.DENIED, pb.STALE,
                    pb.DELETED, pb.UNAVAILABLE, pb.CANCELLED):
                status = pb.UNAVAILABLE
            if status != pb.VERIFIED:
                reply = _empty_reply(operation, request_frame, status)
            # Synchronous publication while host lease is STILL held.
            lease.publish(encode_frame(reply))
            return DeliveryReceipt(reply.status, True)
    except Exception:
        # Do not echo exceptions or source data to the untrusted caller.
        return DeliveryReceipt(pb.UNAVAILABLE, False)
