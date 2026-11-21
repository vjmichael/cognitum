"""R5 exact-original Linux cgroup recovery binding (host-only, no service).

The previously reviewed kernel cgroup2 P46R6 host_recovery owns kill/empty
observations; this module only binds its durable job id and kernel scope to
the original Cognitum R4 HMAC launch record. No arbitrary PID/cgroup path
may be supplied to recovery. An authorized installed service manager must
call reconcile after restart, with delegated cgroup-v2 custody. Neither
inspection nor kernel cleanup allows reexecution, publishing, grants or ACK.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys

from .ssm_r4_protected import (
    DurableOriginalWorkerClaim, NativeSSMCustodyRefused,
    _need, _read_record, _write_once,
)

SCHEMA = "cognitum.ssm_r5.exact_original_linux_cgroup_binding.v1"
JOB = re.compile(r"[a-f0-9]{32}\Z", re.ASCII)


class OriginalLinuxCgroupRecovery:
    def __init__(self, *, claim, delegated_root):
        _need(type(claim) is DurableOriginalWorkerClaim,
              "exact original durable claim object")
        _need(sys.platform.startswith("linux"), "Linux kernel only")
        _need(type(delegated_root) is str and
              delegated_root.startswith("/") and
              not Path(delegated_root).is_symlink(),
              "host-selected real absolute cgroup root")
        self.claim = claim
        self.root = Path(delegated_root)
        self._link = claim._root / (
            "ssm-r5-cgroup-" + claim._identity + ".json")

    def bind_before_worker(self, *, original_nonce, watchkeeper_job_id):
        """Call only after existing P46R6 kernel prelaunch record was fsynced.

        No execution is permitted if this precise original-to-cgroup binding
        cannot be written and verified before the worker process is spawned.
        """
        from cognitum import host_recovery as host
        _need(type(original_nonce) is str and len(original_nonce) == 32 and
              re.fullmatch(r"[a-f0-9]{32}", original_nonce) is not None and
              type(watchkeeper_job_id) is str and
              JOB.fullmatch(watchkeeper_job_id) is not None,
              "bounded trusted watchkeeper identity")
        original = self.claim._verify(_read_record(self.claim._pending))
        _need(original.get("identity") == self.claim._identity and
              original.get("nonce") == original_nonce and
              original.get("phase") == "PRELAUNCH",
              "original prelaunch HMAC binding")
        fd = host._private_fd(self.claim._root)
        try:
            kernel = host._read_record(
                fd, "p46r6-pending-" + watchkeeper_job_id + ".json")
        finally:
            os.close(fd)
        _need(kernel["production_authorized"] is False and
              kernel["job_id"] == watchkeeper_job_id and
              kernel["scope_name"].startswith("cognitum-fixture-"),
              "kernel host recovery job cannot be production authority")
        body = {
            "schema": SCHEMA, "original_identity": self.claim._identity,
            "original_nonce": original_nonce,
            "original_request_sha256": original["request_sha256"],
            "watchkeeper_job_id": watchkeeper_job_id,
            "scope_name": kernel["scope_name"],
            "scope_device": kernel["scope_device"],
            "scope_inode": kernel["scope_inode"],
            "boot_id": kernel["boot_id"],
            "kernel_root_device": kernel["root_device"],
            "kernel_root_inode": kernel["root_inode"],
            "production_authorized": False,
        }
        _write_once(self.claim._root, self._link.name, self.claim._signed(body))
        return self.inspect_original_binding()

    def inspect_original_binding(self):
        from cognitum import host_recovery as host
        original = self.claim._verify(_read_record(self.claim._pending))
        body = self.claim._verify(_read_record(self._link))
        _need(type(body) is dict and
              set(body) == {
                  "schema", "original_identity", "original_nonce",
                  "original_request_sha256", "watchkeeper_job_id",
                  "scope_name", "scope_device", "scope_inode", "boot_id",
                  "kernel_root_device", "kernel_root_inode",
                  "production_authorized",
              } and
              body["schema"] == SCHEMA and
              body["original_identity"] == self.claim._identity and
              body["original_nonce"] == original["nonce"] and
              body["original_request_sha256"] == original["request_sha256"] and
              body["production_authorized"] is False,
              "foreign or altered original cgroup binding")
        fd = host._private_fd(self.claim._root)
        try:
            kernel = host._read_record(
                fd, "p46r6-pending-" + body["watchkeeper_job_id"] + ".json")
        finally:
            os.close(fd)
        _need(kernel["scope_name"] == body["scope_name"] and
              kernel["scope_device"] == body["scope_device"] and
              kernel["scope_inode"] == body["scope_inode"] and
              kernel["boot_id"] == body["boot_id"] and
              kernel["root_device"] == body["kernel_root_device"] and
              kernel["root_inode"] == body["kernel_root_inode"] and
              kernel["production_authorized"] is False,
              "recovery kernel scope differs from original durable record")
        return dict(
            binding_verified_against_local_HMAC=True,
            job_id=body["watchkeeper_job_id"],
            original_operation_reexecution_authorized=False,
            real_installed_service_verified=False,
            independently_signed_stop_verified=False,
        )

    def reconcile_after_restart(self, *, execute=False):
        """Real kernel recovery only through host_recovery on exact linked job.

        execute=False never writes cgroup.kill. execute=True still requires
        existing kernel cgroup2 scope, boot identity and inode equivalence.
        No result is a Lu authorization or signed independent stop proof.
        """
        from cognitum import host_recovery as host
        _need(type(execute) is bool, "explicit trusted host recovery mode")
        bound = self.inspect_original_binding()
        outcome = host.reconcile_job(
            self.claim._root, self.root, bound["job_id"], execute=execute)
        _need(type(outcome) is dict and
              outcome.get("job_id") == bound["job_id"] and
              outcome.get("production_authorized") is False and
              outcome.get("independent_attestation") is False,
              "untrusted kernel recovery result")
        return dict(
            status=outcome["status"],
            original_operation_bound=True,
            kernel_cgroup_reconciliation_claim=outcome,
            automatic_original_reexecution_authorized=False,
            installed_service_stop_verified=False,
            output_delivery_authorized=False,
            output_acknowledgment_authorized=False,
        )
