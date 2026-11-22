"""R3-R1 read-only source-level interruption/restart/replay reconciliation.

This checks immutable original SCM-generated candidate files. It NEVER repairs,
deletes, promotes, replays, or publishes an operation and cannot create a Core
grant or a machine signer. In particular, a signed terminal merely confirms
the prior candidate bytes: it does not establish independent antirollback.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from cog_r3r1_qualifier_cng_verify import (
    REQUIRED_PRELAUNCH, parse, valid_sha, verify_exact,
)

def _sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def assess(*,prelaunch:bytes|None,terminal:bytes|None,signature:bytes|None,
           public_blob:bytes,request:bytes,answer:bytes,external_pin:str)->str:
    """Conservative read-only decision. Every return remains a NO-RETRY hold.

    A missing prelaunch is not evidence of freshness: someone could have
    deleted or rolled it back. Only the independent authority can create
    a NEW original operation after separate reconciliation.
    """
    if prelaunch is None:
        return "UNANCHORED_OR_ROLLED_BACK_HOLD"
    try:
        prior=parse(prelaunch,REQUIRED_PRELAUNCH)
        if not (
            prior["schema"]=="cognitum.ssm.r3r1.ci_prelaunch_uncertain_v1"
            and prior["original_request_sha256"]==_sha(request)
            and valid_sha(prior["pinned_python_sha256"])
            and valid_sha(prior["pinned_child_sha256"])
            and prior["worker_may_have_started"] is True
            and prior["replay_after_restart_permitted"] is False
            and prior["independent_antirollback_verified"] is False
            and prior["original_Lu_Core_grant_verified"] is False
            and prior["output_or_ACK_authorized"] is False
        ):
            return "PRELAUNCH_TAMPER_OR_ROLLBACK_HOLD"
    except (ValueError,TypeError):
        return "PRELAUNCH_TAMPER_OR_ROLLBACK_HOLD"
    if terminal is None and signature is None:
        return "INTERRUPTED_PRELAUNCH_UNCERTAIN_HOLD"
    if terminal is None or signature is None:
        return "PARTIAL_TERMINAL_UNCERTAIN_HOLD"
    try:
        verify_exact(terminal,signature,public_blob,request,answer,
                     external_pin,prelaunch)
    except (ValueError,TypeError):
        return "TERMINAL_TAMPER_OR_ROLLBACK_HOLD"
    return "SIGNED_CANDIDATE_REPLAY_HELD"

def main():
    if os.name!="nt" or os.environ.get("GITHUB_ACTIONS")!="true":
        raise RuntimeError("Native Windows disposable CI original required")
    root=Path(os.environ["GITHUB_WORKSPACE"])/"native/windows_scm_production/target"
    host=root/"q-host"
    io=root/"q-io"
    pre=(host/"production-prelaunch.json").read_bytes()
    term=(host/"production-terminal.json").read_bytes()
    signed=(host/"production-terminal-signed.json").read_bytes()
    blob=(host/"r2-public-p256.blob").read_bytes()
    request=(io/"input.frame").read_bytes()
    answer=(io/"output.frame").read_bytes()
    pin=os.environ["COG_R2_CI_PUBLIC_SHA256"]
    receipts=json.loads(Path("q-scm-receipt.json").read_text("utf-8"))
    if (receipts["second_SCM_start_same_original_replay_denied"] is not True
        or receipts["exact_durable_prelaunch_and_signed_terminal_unchanged_on_restart"] is not True
        or receipts["independent_antirollback_accepted"] is not False):
        raise AssertionError("Actual SCM second-start denial evidence missing")
    cases={
      "signed_candidate":((pre,term,signed),"SIGNED_CANDIDATE_REPLAY_HELD"),
      "crash_after_prelaunch":((pre,None,None),"INTERRUPTED_PRELAUNCH_UNCERTAIN_HOLD"),
      "crash_after_terminal_sync":((pre,term,None),"PARTIAL_TERMINAL_UNCERTAIN_HOLD"),
      "signer_only":((pre,None,signed),"PARTIAL_TERMINAL_UNCERTAIN_HOLD"),
      "missing_prelaunch":((None,term,signed),"UNANCHORED_OR_ROLLED_BACK_HOLD"),
      "corrupt_prelaunch":((pre+b"\x00",term,signed),"PRELAUNCH_TAMPER_OR_ROLLBACK_HOLD"),
      "altered_original_terminal":((pre,term+b" ",signed),"TERMINAL_TAMPER_OR_ROLLBACK_HOLD"),
      "altered_signature":((pre,term,signed.replace(b'"Core_grant_verified":false',
                                                    b'"Core_grant_verified":true')),
                           "TERMINAL_TAMPER_OR_ROLLBACK_HOLD"),
      "missing_all":((None,None,None),"UNANCHORED_OR_ROLLED_BACK_HOLD"),
    }
    for name,(items,expected) in cases.items():
        outcome=assess(prelaunch=items[0],terminal=items[1],
                       signature=items[2],public_blob=blob,
                       request=request,answer=answer,external_pin=pin)
        if outcome!=expected:
            raise AssertionError(name+": expected "+expected+", got "+outcome)
    print(json.dumps({
      "schema":"cognitum.ssm.r3r1.ci_recovery_decision_matrix.v1",
      "status":"PASS_CI_NATIVE_SCM_RESTART_UNCERTAIN_REPLAY_FAIL_CLOSED",
      "exact_original_SCM_restarted_without_reexecution":True,
      "original_signed_candidate_replay_held":True,
      "interruption_and_corruption_cases_refused":len(cases),
      "independent_antirollback_verified":False,
      "installed_production_custody_approved":False,
      "original_Lu_Core_grant_verified":False,
      "output_or_ACK_authorized":False,
    },sort_keys=True))

if __name__=="__main__":
    main()
