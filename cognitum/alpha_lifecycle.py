"""P2 standalone alpha worker lifecycle and revocable local host-leases.

This is a *test reference* for a future trusted host. Anyone importing Python
can call grant(), so it confers NO Lu authority, consent, or OS sandboxing.
A call is released only by locked_publish after fresh state/epoch checks.
"""
from __future__ import annotations

from dataclasses import dataclass
import secrets
import struct
import subprocess
import sys
import threading
import time

from .alpha_native import (HostAdmission, ID, MAX_FRAME, MAX_REPLY,
                           RATIONAL_RESULT_TYPE, ALLOWED, _parse)
from .protobuf_codec import decode_rational_request, decode_success
from .proto import alpha_native_pb2 as proto
from .plugins.calculator import calculate

POLL_SECONDS = 0.05


@dataclass(frozen=True, slots=True)
class LocalTicket:
    nonce: str
    conversation_id: str
    request_id: str
    epoch: int


class LocalLeaseBoard:
    """Local in-memory grant simulation, not an authenticated host authority."""
    def __init__(self):
        self._lock = threading.RLock()
        self._epochs: dict[str, int] = {}
        self._tickets: dict[str, tuple[LocalTicket, HostAdmission]] = {}
        self._revoked: set[str] = set()

    def grant(self, conversation_id: str, request_id: str, *, timeout_ms: int = 5000):
        if not ID.fullmatch(conversation_id) or not ID.fullmatch(request_id):
            raise ValueError('INVALID_LOCAL_IDENTITY')
        admission = HostAdmission(conversation_id, request_id,
                                  frozenset({'calc.rational'}), True, timeout_ms)
        with self._lock:
            if conversation_id in self._revoked:
                raise PermissionError('CONVERSATION_REVOKED')
            if any(t.conversation_id == conversation_id and t.request_id == request_id
                   for t, _ in self._tickets.values()):
                raise ValueError('DUPLICATE_ACTIVE_REQUEST')
            ticket = LocalTicket(secrets.token_hex(16), conversation_id,
                                 request_id, self._epochs.get(conversation_id, 0))
            self._tickets[ticket.nonce] = (ticket, admission)
            return ticket

    def _current(self, ticket: LocalTicket) -> HostAdmission:
        if type(ticket) is not LocalTicket:
            raise PermissionError('INVALID_LOCAL_TICKET')
        with self._lock:
            active = self._tickets.get(ticket.nonce)
            if (active is None or active[0] != ticket
                or ticket.conversation_id in self._revoked
                or self._epochs.get(ticket.conversation_id, 0) != ticket.epoch):
                raise PermissionError('LEASE_REVOKED_OR_COMPLETED')
            return active[1]

    def cancel(self, ticket: LocalTicket) -> None:
        with self._lock:
            self._current(ticket)
            del self._tickets[ticket.nonce]

    def revoke(self, conversation_id: str) -> None:
        if not ID.fullmatch(conversation_id):
            raise ValueError('INVALID_LOCAL_IDENTITY')
        with self._lock:
            self._revoked.add(conversation_id)
            self._epochs[conversation_id] = self._epochs.get(conversation_id, 0) + 1
            for nonce, (ticket, _) in list(self._tickets.items()):
                if ticket.conversation_id == conversation_id:
                    del self._tickets[nonce]

    def locked_publish(self, ticket: LocalTicket, result: bytes, sink) -> None:
        """Hold the same lock through the final recheck and delivery callback."""
        with self._lock:
            self._current(ticket)
            if not callable(sink):
                raise TypeError('HOST_SINK_REQUIRED')
            # A failed sink does not consume the ticket, but cannot publish unapproved.
            sink(result)
            self._tickets.pop(ticket.nonce, None)


def run_guarded(call_wire: bytes, board: LocalLeaseBoard, ticket: LocalTicket,
                sink) -> None:
    """Bounded subprocess and suppress delivery after cancel/revoke/deadline.

    The real Lu supervisor must supply authenticated tokens, OS Job Objects,
    child-tree cleanup, persisted revocation and trusted delivery. The local
    worker is trusted Python and child.kill() only kills its direct process.
    """
    if type(board) is not LocalLeaseBoard:
        raise TypeError('LOCAL_LEASE_BOARD_REQUIRED')
    admission = board._current(ticket)
    started = time.monotonic()
    request = _parse(proto.Call, call_wire, MAX_FRAME)
    if (request.version != 1 or not ID.fullmatch(request.request_id)
        or request.request_id != admission.request_id
        or request.operation != 'calc.rational'
        or request.operation not in admission.operations
        or request.request_type_url != ALLOWED['calc.rational']):
        raise PermissionError('REQUEST_NOT_ADMITTED')
    expression = decode_rational_request(request.request_type_url, request.request_payload)
    expected = calculate(expression)  # no model-controlled executable or arbitrary code
    board._current(ticket)
    frame = struct.pack('>I', len(call_wire)) + call_wire
    child = subprocess.Popen([sys.executable, '-m', 'cognitum.alpha_native_worker'],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    first_communicate = True
    try:
        while True:
            board._current(ticket)
            remaining = admission.timeout_ms / 1000 - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError('ALPHA_LIFECYCLE_DEADLINE')
            try:
                stdout, stderr = child.communicate(input=frame if first_communicate else None,
                                                   timeout=min(POLL_SECONDS, remaining))
                break
            except subprocess.TimeoutExpired:
                first_communicate = False
                continue
        board._current(ticket)
        if child.returncode or stderr or len(stdout) < 4 or len(stdout) > MAX_REPLY+4:
            raise ValueError('ALPHA_WORKER_FAILED_OR_TOO_LARGE')
        n = struct.unpack('>I', stdout[:4])[0]
        if not n or n > MAX_REPLY or len(stdout) != n+4:
            raise ValueError('ALPHA_REPLY_FRAME_MISMATCH')
        reply_wire = stdout[4:]
        reply = _parse(proto.Reply, reply_wire, MAX_REPLY)
        if (reply.version != 1 or reply.request_id != ticket.request_id
            or reply.status != proto.Reply.COMPLETED or reply.error_code
            or reply.lu_integrated or reply.os_isolation_verified
            or reply.result_type_url != RATIONAL_RESULT_TYPE):
            raise ValueError('ALPHA_REPLY_INVALID_OR_FORGED')
        value = decode_success('calc.rational', reply.result_type_url, reply.result_payload,
                               request_id=ticket.request_id,
                               correlation_id=ticket.conversation_id)
        if value.value.value != expected:
            raise ValueError('WORKER_RESULT_MISMATCH')
        if time.monotonic() - started >= admission.timeout_ms / 1000:
            raise TimeoutError('ALPHA_LIFECYCLE_DEADLINE')
        board.locked_publish(ticket, reply_wire, sink)
    finally:
        if child.poll() is None:
            child.kill()  # direct child only: NOT an OS-enforced descendant kill
        child.communicate()
