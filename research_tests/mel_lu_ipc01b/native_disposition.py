"""Capture original native OS-transport test disposition without Core claims."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

REQUIRED={
"test_linux_native_uds_auth_health_over_real_os_socket",
"test_linux_native_peer_uid_and_private_socket_refusals",
"test_linux_native_authentication_rejects_forged_core",
"test_windows_native_named_pipe_auth_health",
"test_windows_os_observed_process_image_pin_mismatch_refusal",
"test_windows_named_pipe_path_and_incomplete_identity_pin_refused",
"test_no_generic_client_server_or_model_permissions",
"test_trusted_host_preflight_fails_closed_with_absent_real_core",
}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--junit",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    cases=list(ET.parse(args.junit).getroot().iter("testcase"))
    names=[(x.get("classname"),x.get("name")) for x in cases]
    assert len(cases)==38,(len(cases),"unexpected native IPC test count")
    assert len(set(names))==len(names)
    assert not any(x.find(tag) is not None for x in cases
                   for tag in ("error","failure","skipped"))
    assert all(sum(n==needle for cls,n in names)==1 for needle in REQUIRED)
    assert sys.platform=="win32" or sys.platform.startswith("linux")
    is_windows=sys.platform=="win32"
    result=dict(schema="cognitum.lu_ipc01b.original_native_transport.v1",
      test_cases_passed=len(cases),native_os=sys.platform,
      backend=("win32_named_pipe_overlapped_os_process_pin" if is_windows
               else "linux_af_unix_so_peercred_private_inode"),
      native_byte_stream_test_exercised=True,
      native_test_server_is_real_lu_core=False,
      real_installed_core_health_exercised=False,
      signed_peer_publisher_qualified=False,
      installed_enrolled_credentials_qualified=False,
      model_tool_invocation_authorized=False,
      no_test_skips=True)
    Path(args.output).write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
