"""R5 Linux original-operation restart refusal without fake cgroup success.

Positive kernel-delegated cgroup restart acceptance must run on a genuinely
delegated Linux host, never from synthetic directories or a no-op fake kernel.
These tests inspect genuine local cgroup readiness and verify that a missing
or forged operation↔watchkeeper binding cannot invoke kernel recovery.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import uuid

import pytest

from cognitum.mel import admission as mel
from cognitum.mel import ssm_r4_protected as r4
from cognitum.mel import ssm_r5_linux_recovery as linux
from cognitum.mel.ssm_os_credentials import OSCredentialBroker,CredentialUnavailable
from cognitum.mel.vendor.lu.workspace.v0 import workspace_pb2 as lu
from cognitum.cgroup2_contract import preflight
from cognitum import host_recovery as kernel

SCOPE=mel.Scope("recovery-session","workspace","subject","turn")
ORIGIN=lu.OriginRefs(workspace_ref="workspace",conversation_ref="conversation",
                     user_turn_ref="turn",task_ref="task",
                     operation_ref="r5-recovery-operation")
KEY=bytes(range(32))


def _host(tmp_path):
    root=tmp_path/"precreated-protected"
    root.mkdir(mode=0o700)
    if os.name=="posix":
        root.chmod(0o700)
    broker=OSCredentialBroker(root,namespace="r5linux-"+uuid.uuid4().hex)
    try:
        broker.provision(SCOPE,ORIGIN.operation_ref,KEY)
    except CredentialUnavailable:
        if sys.platform=="win32":
            pytest.fail("Windows DPAPI credential prerequisite")
        return root,None
    return root,broker


def test_no_cross_platform_or_unpinned_cgroup_recovery(tmp_path):
    root,broker=_host(tmp_path)
    if broker is None:return
    try:
        claim=r4.DurableOriginalWorkerClaim(
            root,broker,SCOPE,ORIGIN,SCOPE.session,"event","stream")
        if sys.platform!="linux":
            with pytest.raises(r4.NativeSSMCustodyRefused,match="Linux"):
                linux.OriginalLinuxCgroupRecovery(
                    claim=claim,delegated_root="/sys/fs/cgroup")
        else:
            with pytest.raises(r4.NativeSSMCustodyRefused,match="cgroup root"):
                linux.OriginalLinuxCgroupRecovery(
                    claim=claim,delegated_root="relative/path")
    finally:
        broker.revoke(SCOPE,ORIGIN.operation_ref)


def test_linux_existing_kernel_delegation_is_reported_not_invented():
    if sys.platform!="linux":
        return
    status=preflight("/sys/fs/cgroup")
    assert type(status.kernel_cgroup2) is bool
    assert type(status.admitted_for_fixture) is bool
    # This result never licenses the original MEL operation.
    assert status.reason
    assert not hasattr(linux,"create_lu_core_grant")


def test_missing_exact_original_cgroup_link_blocks_recovery(tmp_path,monkeypatch):
    if sys.platform!="linux":
        return
    root,broker=_host(tmp_path)
    if broker is None:return
    try:
        claim=r4.DurableOriginalWorkerClaim(
            root,broker,SCOPE,ORIGIN,SCOPE.session,"event","stream")
        claim.before_worker("a"*64)
        recovery=linux.OriginalLinuxCgroupRecovery(
            claim=claim,delegated_root="/sys/fs/cgroup")
        def forbidden(*args,**kwargs):
            raise AssertionError("unbound recovery reached kernel execution")
        monkeypatch.setattr(kernel,"reconcile_job",forbidden)
        with pytest.raises((OSError,r4.NativeSSMCustodyRefused)):
            recovery.reconcile_after_restart(execute=True)
        assert claim.restart_assessment().startswith("UNCERTAIN")
    finally:
        broker.revoke(SCOPE,ORIGIN.operation_ref)


def test_local_forged_cgroup_link_cannot_launder_a_kernel_stop(tmp_path,monkeypatch):
    if sys.platform!="linux":
        return
    root,broker=_host(tmp_path)
    if broker is None:return
    try:
        claim=r4.DurableOriginalWorkerClaim(
            root,broker,SCOPE,ORIGIN,SCOPE.session,"event","stream")
        nonce=claim.before_worker("a"*64)
        recovery=linux.OriginalLinuxCgroupRecovery(
            claim=claim,delegated_root="/sys/fs/cgroup")
        forged=dict(
            schema=linux.SCHEMA,original_identity=claim._identity,
            original_nonce=nonce,original_request_sha256="f"*64,
            watchkeeper_job_id="a"*32,
            scope_name="cognitum-fixture-"+("b"*24),
            scope_device=1,scope_inode=2,boot_id="fake",
            kernel_root_device=3,kernel_root_inode=4,
            production_authorized=False)
        r4._write_once(root,recovery._link.name,claim._signed(forged))
        monkeypatch.setattr(kernel,"reconcile_job",
                            lambda *a,**kw: (_ for _ in ()).throw(
                                AssertionError("forged link invoked real kernel")))
        with pytest.raises(r4.NativeSSMCustodyRefused,match="foreign or altered"):
            recovery.reconcile_after_restart(execute=True)
        assert claim.restart_assessment().startswith("UNCERTAIN")
    finally:
        broker.revoke(SCOPE,ORIGIN.operation_ref)


def test_host_kernel_restart_api_never_authorizes_result():
    # No adapter may silently assert installed or Lu execution authority.
    assert not hasattr(linux,"authorize_execution")
    assert not hasattr(linux,"publish")
    assert not hasattr(linux,"acknowledge")
    assert not hasattr(linux,"enroll_lu_issuer")
