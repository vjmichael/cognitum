"""COG-LU-IPC-01A: source-locked, inert Lu workspace v0 provider proposal."""
import copy

import pytest

from cognitum.mel import lu_workspace_contract as ipc


def test_exact_five_inert_pure_compute_descriptors():
    offer=ipc.proposal()
    assert offer["lu_source_sha"]==ipc.LU_REVIEWED_SOURCE_SHA
    assert offer["lu_proto_git_blob_sha"]==ipc.LU_WORKSPACE_PROTO_GIT_BLOB
    assert (offer["protocol_major"],offer["protocol_minor"]) == (1,0)
    assert offer["register_workspace"]["module_id"]=="cognitum.mel"
    assert offer["register_workspace"]["kind"]=="MODULE_ROLE_CORE_EXTENSION"
    caps=offer["register_workspace"]["capabilities"]
    assert len(caps)==5
    assert {x["capability_id"] for x in caps}=={"cognitum."+x for x in ipc.REVIEWED_OPERATIONS}
    assert all(x["declared_effects"]==["EFFECT_CLASS_PURE_COMPUTE"] for x in caps)
    assert all(x["capability_version"]==1 and not x["streams_progress"] for x in caps)
    assert len(offer["reviewed_mel_bindings"])==5
    for key in ("registered","model_advertised","connection_authenticated",
                "pure_compute_host_bridge_qualified","execution_authorized",
                "installed_service_qualified","host_grant_issued"):
        assert offer[key] is False


def test_deterministic_proposal_and_no_ssm_registration_without_codec():
    assert ipc.proposal()==ipc.proposal()
    p=ipc.proposal()
    assert p["pending_ssm_operation"]==ipc.SSM_PENDING_OPERATION
    assert all("ssm" not in c["capability_id"]
               for c in p["register_workspace"]["capabilities"])
    assert len(bytes.fromhex(p["candidate_manifest_sha256"]))==32


def test_source_blob_pin_drift_refused():
    assert ipc.validate_external_lu_proto_blob(ipc.LU_WORKSPACE_PROTO_GIT_BLOB)
    with pytest.raises(ValueError,match="source drift"):
        ipc.validate_external_lu_proto_blob("0"*40)
    with pytest.raises(ValueError,match="source drift"):
        ipc.validate_external_lu_proto_blob(None)


@pytest.mark.parametrize("effect,cap,bridge",[
    ("EFFECT_CLASS_READ_WORKSPACE","cognitum.hdc.bind",False),
    ("EFFECT_CLASS_PURE_COMPUTE","cognitum.ssm.fixed_duration.advance.v1",False),
    ("EFFECT_CLASS_PURE_COMPUTE","cognitum.hdc.bind",False),
    ("EFFECT_CLASS_PURE_COMPUTE","cognitum.hdc.bind",True),
])
def test_no_model_facing_effect_or_implicit_grant(effect,cap,bridge):
    with pytest.raises(ValueError,match="refused"):
        ipc.refuse_unsupported_invoke(effect,cap,host_pure_bridge=bridge)


def test_reviewed_route_change_fails_closed(monkeypatch):
    from cognitum.mel import lu_adapter
    original=lu_adapter.proposal()
    changed=copy.deepcopy(original)
    changed["routes"][0]["required_effect"]="read_workspace"
    monkeypatch.setattr(lu_adapter,"proposal",lambda:changed)
    with pytest.raises(ValueError,match="unapproved effect"):
        ipc.proposal()


def test_unrecognized_native_type_url_fails_closed(monkeypatch):
    from cognitum.mel import lu_adapter
    changed=copy.deepcopy(lu_adapter.proposal())
    changed["routes"][0]["input_type_url"]="text/plain"
    monkeypatch.setattr(lu_adapter,"proposal",lambda:changed)
    with pytest.raises(ValueError,match="Protobuf type URLs"):
        ipc.proposal()
