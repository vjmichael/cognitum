"""COG-LU-IPC-01E-R2: native OS-key / local revision-CAS adapter.

Reuses installed-host-facing Cognitum R6 custody objects:
- OSCredentialBroker (Win32 DPAPI current-user or Linux kernel keyring)
- LocalAuthenticatedRevisionCAS (separately protected local SQLite HMAC CAS)

This bridges the strict 01D Lu original-operation chain's tuple interface to
the original MEL Scope. It NEVER provisions/rotates credentials, chooses a
path, creates a revision authority, authenticates Lu Core, verifies a signed
publisher, or grants mathematical/output execution. The host must enroll
native secrets and create the revision file independently.

Local CAS is not a physical/remote monotonic counter. It cannot qualify
cross-file rollback resistance, installer ACLs or genuine installed custody.
"""
from __future__ import annotations

import hmac

from . import admission as mel
from . import lu_ipc_lifecycle as lifecycle
from . import lu_ssm_contract as typed
from .ssm_os_credentials import OSCredentialBroker
from .ssm_revision_cas import LocalAuthenticatedRevisionCAS
from .vendor.lu.workspace.v0 import workspace_pb2 as lu

SCHEMA="cognitum.lu_ipc01e_r2.native_custody_adapter.v1"


def _need(condition, reason):
    if not condition:
        raise ValueError("Cognitum native IPC custody refused: "+reason)


class OriginalLuOperationNativeCustody:
    """Closed scope-bound shim. No own signing, secrets, bootstrap or fallback."""

    def __init__(self, *, trusted_origin, mel_scope, core_session_ref,
                 credential_broker, local_revision_cas):
        _need(type(trusted_origin) is lu.OriginRefs,"trusted original Lu scope")
        self._original=typed._origin(trusted_origin)
        _need(type(mel_scope) is mel.Scope, "real reviewed host MEL Scope")
        self._session=lifecycle._text(core_session_ref,"original Core session ref")
        _need(self._original[0]==mel_scope.workspace and
              self._original[2]==mel_scope.turn and
              mel_scope.session==self._session,
              "cross Core session/workspace/user-turn custody")
        _need(type(credential_broker) is OSCredentialBroker and
              type(local_revision_cas) is LocalAuthenticatedRevisionCAS,
              "genuine OS broker and explicit separate local CAS required")
        _need(local_revision_cas._broker is credential_broker,
              "same exactly pinned OS custody secret provider")
        self._mel_scope=mel_scope
        self._broker=credential_broker
        self._cas=local_revision_cas
        self._operation=self._original[-1]

    def _check(self,original_scope,operation_ref):
        _need(type(original_scope) is tuple and
              original_scope==self._original and
              type(operation_ref) is str and
              operation_ref==self._operation,
              "original Lu operation/scope replay or foreign session")

    def borrow_key(self,original_scope,operation_ref):
        """Same native OS key used to HMAC R1 original operation log."""
        self._check(original_scope,operation_ref)
        return self._broker.borrow_key(self._mel_scope,self._operation)

    def read(self,original_scope,operation_ref):
        """Mapping only; never treat local CAS as independent hardware proof."""
        self._check(original_scope,operation_ref)
        revision,digest=self._cas.read(self._mel_scope,self._operation)
        _need(type(revision) is int and revision>=0,
              "native CAS revision")
        if revision==0:
            _need(digest is None,"empty native CAS state")
            return 0,lifecycle.ZERO
        _need(type(digest) is str and len(digest)==64,
              "native CAS head digest")
        return revision,digest

    def advance(self,original_scope,operation_ref,old_rev,old_sha,
                new_rev,new_sha):
        """Delegates original exact compare-and-swap; never fast-forwards."""
        self._check(original_scope,operation_ref)
        _need(type(old_rev) is int and type(new_rev) is int and
              0<=old_rev<new_rev<=lifecycle.MAX_RECORDS,
              "strict bounded original operation revision")
        _need(type(old_sha) is str and type(new_sha) is str and
              len(old_sha)==64 and len(new_sha)==64,
              "strict original head SHA shape")
        self._cas.advance(
            self._mel_scope,self._operation,old_rev,
            None if old_rev==0 and old_sha==lifecycle.ZERO else old_sha,
            new_rev,new_sha)
        observed=self.read(original_scope,operation_ref)
        _need(observed==(new_rev,new_sha),
              "native local CAS post-commit mismatch/uncertain")
        return True

    def evidence(self):
        return dict(
            schema=SCHEMA,
            native_os_credential_backend=self._broker.backend,
            actual_native_os_broker_object_used=True,
            local_authenticated_revision_CAS_used=True,
            genuine_installed_core_session_verified=False,
            external_independent_monotonic_anchor_verified=False,
            installer_ACL_custody_verified=False,
            separately_supervised_worker_lifecycle_verified=False,
            original_Lu_sourced_signed_receipt_verified=False,
            model_tool_execution_authorized=False,
            output_delivery_authorized=False,
            output_acknowledgment_authorized=False,
        )
