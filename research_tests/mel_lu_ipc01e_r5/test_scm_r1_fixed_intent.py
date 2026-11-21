"""R1 test-only SCM original-operation staged intent and numerical reply checks.

Not a Core authorization test: the local random CI MAC key is recoverable
from a test executable. No production service may accept these credentials.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest

from scripts import cog_r5_r1_scm_ssm_fixture as fixture


def test_ci_stage_generates_closed_actual_ssm_data_and_ephemeral_auth(tmp_path):
    home=tmp_path/"attempt"
    home.mkdir()
    envfile=tmp_path/"fixture-env"
    receipt=fixture.prepare(home,envfile)
    assert receipt["schema"]=="cognitum.ssm.r1.staged_test_only.v1"
    assert not receipt["installed_core_enrollment"]
    assert not receipt["independent_signer"]
    frame=json.loads((home/"input.frame").read_bytes())
    assert frame["operation"]=="ssm.fixed_duration.advance.research"
    assert set(frame["payload"])=={"state","kind","end_time","increment"}
    assert frame["payload"]["kind"]=="increment"
    assert frame["payload"]["increment"]==[.2]
    assert frame["payload"]["end_time"]==.3
    original=(home/"intent.frame").read_bytes().split(b"\n")
    assert len(original)==3 and original[-1]==b""
    parts=original[0].decode("ascii").split("\t")
    assert len(parts)==12
    assert parts[3]=="ci-user-turn"
    assert parts[5]=="ci-original-operation"
    assert parts[10]==hashlib.sha256((home/"input.frame").read_bytes()).hexdigest()
    values={}
    for item in envfile.read_text().splitlines():
        k,v=item.split("=",1)
        values[k]=v
    key=bytes.fromhex(values["COG_R1_CI_MAC_KEY_HEX"])
    assert len(key)==32
    assert hmac.compare_digest(
        hmac.new(key,fixture.DOMAIN+original[0],hashlib.sha256).hexdigest(),
        original[1].decode("ascii"))
    assert all(not (home/n).exists()
               for n in ("output.frame","stop.json","prelaunch.json"))
    with pytest.raises(ValueError,match="existing R1"):
        fixture.prepare(home,envfile)


def test_external_numeric_output_is_not_a_service_stop_or_release(tmp_path):
    home=tmp_path/"attempt"
    home.mkdir()
    envfile=tmp_path/"fixture-env"
    fixture.prepare(home,envfile)
    with pytest.raises(FileNotFoundError):
        fixture.verify(home)
    (home/"output.frame").write_text('{"status":"ok","reply":{}}')
    with pytest.raises(FileNotFoundError):
        fixture.verify(home)


def test_service_stop_receipt_is_not_issued_by_python_staging_module():
    for name in (
        "sign_stop","issue_core_grant","installed_health",
        "permit_output_release","open_private_core_scm_control",
        "install_signed_service","acknowledge_external_output",
    ):
        assert not hasattr(fixture,name)
