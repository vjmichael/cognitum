"""Run genuine OS secret custody and local CAS evidence on a native runner.

No fake provider, no fallback. Linux keyrings can be denied by kernel policy:
report that as UNAVAILABLE rather than claiming a native pass.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import secrets
import sys
import tempfile

from cognitum.mel import admission as mel
from cognitum.mel import ssm_os_credentials as creds
from cognitum.mel import ssm_revision_cas as cas


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    scope=mel.Scope("native","workspace","subject","turn")
    result=dict(schema="cognitum.ssm04r6int02.native_OS_custody.v1",
        os=sys.platform,
        backend="windows_dpapi_current_user" if sys.platform=="win32"
                else "linux_kernel_user_keyring",
        os_native_credential_qualified=False,
        local_revision_CAS_qualified=False,
        hardware_monotonic_revision_qualified=False,
        os_sandbox_worker_qualified=False,
        installed_MEL_route_qualified=False)
    with tempfile.TemporaryDirectory(prefix="cog-r6-os-custody-") as tmp:
        root=Path(tmp)
        if sys.platform.startswith("linux"):
            root.chmod(0o700)
        broker=creds.OSCredentialBroker(root,namespace="native-probe")
        secret=secrets.token_bytes(32)
        try:
            broker.provision(scope,"probe-stream",secret)
        except creds.CredentialUnavailable:
            if sys.platform=="win32":
                raise AssertionError("required Windows DPAPI native custody unavailable")
            result["native_credential_disposition"]="OS_KERNEL_KEYRING_UNAVAILABLE_FAIL_CLOSED"
        else:
            assert broker.borrow_key(scope,"probe-stream")==secret
            assert secret not in b"".join(p.read_bytes() for p in root.iterdir()
                                       if p.is_file())
            anchor=cas.LocalAuthenticatedRevisionCAS(root,broker,
                            namespace="native-probe",create=True)
            assert anchor.read(scope,"probe-stream")==(0,None)
            anchor.advance(scope,"probe-stream",0,None,1,"a"*64)
            anchor.advance(scope,"probe-stream",1,"a"*64,2,"b"*64)
            assert anchor.read(scope,"probe-stream")==(2,"b"*64)
            anchor.close()
            second=cas.LocalAuthenticatedRevisionCAS(root,broker,
                            namespace="native-probe")
            assert second.read(scope,"probe-stream")==(2,"b"*64)
            second.close()
            result["os_native_credential_qualified"]=True
            result["local_revision_CAS_qualified"]=True
            result["native_credential_disposition"]="PASS_OS_NATIVE_CUSTODY_AND_LOCAL_CAS"
            assert broker.revoke(scope,"probe-stream")
            try:broker.borrow_key(scope,"probe-stream")
            except creds.CredentialUnavailable:pass
            else:raise AssertionError("revoked secret remained readable")
    Path(args.output).write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",
                                 encoding="utf-8")
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
