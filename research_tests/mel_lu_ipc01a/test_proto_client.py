"""Pinned Lu protobuf compilation and *synthetic* read-only exchange tests.

The fixture speaks a source-compatible Lu v0 transcript. It is NOT a real
Core server, installed signed package, OS-attested peer or authority witness.
"""
from __future__ import annotations

from hashlib import sha1
import hmac
import hashlib
from pathlib import Path
import struct

import pytest

from cognitum.mel import lu_ipc_readonly as c
from cognitum.mel import lu_workspace_contract as contract
from cognitum.mel.vendor.lu.workspace.v0 import workspace_pb2 as pb

KEY = bytes(range(1, 33))
PACKAGE = b"\xa5"*32
CHALLENGE = b"\x55"*32
SESSION = "lu-core-epoch-1"
EPOCH = "core-epoch-a"


def _wire(message):
    data = message.SerializeToString(deterministic=True)
    return struct.pack(">I",len(data))+data


def _frame(request_id, kind, body, session=""):
    result=pb.WorkspaceFrame(protocol_major=1,protocol_minor=0,
                              request_id=request_id,session_ref=session)
    getattr(result,kind).CopyFrom(body)
    return result


class SyntheticCoreStream:
    """Fragmented in-memory byte exchange; no socket/OS peer simulated."""

    def __init__(self, fault=""):
        self.fault=fault
        self._incoming=bytearray()
        self._outgoing=bytearray()
        self.received=[]
        self.hello_bytes=None
        self.hello_id=None
        self.closed=False
        self.last_health_id=None
        self.proof_verified=False

    def write(self,data):
        assert not self.closed
        n=min(len(data),13)
        self._incoming.extend(data[:n])
        self._drain()
        return n

    def read(self,n):
        assert not self.closed
        take=min(n,17,len(self._outgoing))
        data=bytes(self._outgoing[:take])
        del self._outgoing[:take]
        return data

    def flush(self):pass

    def close(self):self.closed=True

    def _drain(self):
        while len(self._incoming)>=4:
            length=struct.unpack(">I",self._incoming[:4])[0]
            if len(self._incoming)<4+length:return
            raw=bytes(self._incoming[4:4+length])
            del self._incoming[:4+length]
            message=pb.WorkspaceFrame.FromString(raw)
            self.received.append(message.WhichOneof("body"))
            self._respond(message,raw)

    def _enqueue(self,reply):
        raw=_wire(reply)
        if self.fault=="oversize_challenge" and reply.WhichOneof("body")=="auth_challenge":
            raw=struct.pack(">I",c.MAX_FRAME+1)+raw[4:]
        if self.fault=="unknown_challenge_field" and reply.WhichOneof("body")=="auth_challenge":
            # Unknown field #100 varint 1, must fail strict canonical parse.
            malformed=reply.SerializeToString(deterministic=True)+b"\xa0\x06\x01"
            raw=struct.pack(">I",len(malformed))+malformed
        self._outgoing.extend(raw)

    def _respond(self,message,raw):
        kind=message.WhichOneof("body")
        if kind=="hello":
            self.hello_bytes=raw
            self.hello_id=message.request_id
            assert message.hello.claimed_module_id=="cognitum.mel"
            assert message.hello.claimed_role==pb.MODULE_ROLE_CORE_EXTENSION
            assert message.hello.claimed_package_sha256==PACKAGE
            body=pb.AuthChallenge(server_nonce=
                   b"\x00"*32 if self.fault=="zero_challenge" else CHALLENGE)
            reply=_frame(
                "different-request" if self.fault=="challenge_id" else
                message.request_id,"auth_challenge",body)
            if self.fault=="challenge_version":
                reply.protocol_minor=1
            self._enqueue(reply)
        elif kind=="auth_proof":
            expected=hmac.new(KEY,b"lu.workspace.client.v0\x00"+
                              self.hello_bytes+CHALLENGE,hashlib.sha256).digest()
            self.proof_verified=hmac.compare_digest(
                expected,message.auth_proof.client_hmac_sha256)
            unsigned=pb.Welcome(selected_major=1,selected_minor=0,
                                core_epoch_ref=EPOCH)
            signed=hmac.new(KEY,b"lu.workspace.server.v0\x00"+
                            self.hello_bytes+CHALLENGE+
                            SESSION.encode("ascii")+
                            unsigned.SerializeToString(deterministic=True),
                            hashlib.sha256).digest()
            unsigned.server_hmac_sha256=(b"\xff"*32
                            if self.fault=="bad_server_mac" else signed)
            if self.fault=="welcome_version":unsigned.selected_major=2
            reply=_frame(
                "different-request" if self.fault=="welcome_id"
                else message.request_id,"welcome",unsigned,
                session="other-session" if self.fault=="wrong_session_mac"
                else SESSION)
            self._enqueue(reply)
        elif kind=="health":
            self.last_health_id=message.request_id
            assert message.session_ref==SESSION
            response=pb.HealthReport(
                    module_id="foreign.core" if self.fault=="health_foreign_module"
                    else "lu.core",
                    connected=self.fault!="health_disconnected",
                    status_code="DOWN" if self.fault=="health_disconnected"
                    else "READY",
                    epoch=0 if self.fault=="health_zero_epoch" else 7)
            reply=_frame(
                "different-request" if self.fault=="health_id"
                else message.request_id,"health_report",response,
                session="foreign-session" if self.fault=="health_session"
                else SESSION)
            if self.fault=="health_wrong_kind":
                reply=_frame(message.request_id,"health",
                             pb.HealthRequest(),session=SESSION)
            self._enqueue(reply)
        else:
            raise AssertionError("fixture never performs registration/invoke")


def _client(fault=""):
    fake=SyntheticCoreStream(fault)
    return c.AuthenticatedReadOnlyLuClient(fake,
                enrolled_key=KEY,installed_package_sha256=PACKAGE),fake


def test_vendored_git_source_pin_and_native_compiled_generated_descriptor():
    src=(Path(__file__).resolve().parents[2]/
         "cognitum/mel/vendor/lu/workspace/v0/workspace.proto")
    blob=src.read_bytes()
    git_hash=sha1(b"blob "+str(len(blob)).encode()+b"\x00"+blob).hexdigest()
    assert git_hash=="4e01d921197fb1c58c99958479b1cede36e13c9a"
    assert contract.validate_external_lu_proto_blob(git_hash)
    assert pb.DESCRIPTOR.package=="lu.workspace.v0"
    assert pb.MODULE_ROLE_CORE_EXTENSION==2
    assert pb.EFFECT_CLASS_PURE_COMPUTE==1
    assert pb.WorkspaceFrame.DESCRIPTOR.fields_by_name["auth_challenge"].number==36
    assert pb.WorkspaceFrame.DESCRIPTOR.fields_by_name["health"].number==25
    assert pb.WorkspaceFrame.DESCRIPTOR.fields_by_name["health_report"].number==26


def test_five_reviewed_mel_routes_serialize_as_real_lu_descriptors():
    proposed=contract.proposal()
    caps=proposed["register_workspace"]["capabilities"]
    assert len(caps)==5
    for item in caps:
        desc=pb.CapabilityDescriptor(
             capability_id=item["capability_id"],
             capability_version=item["capability_version"],
             input_type_url=item["input_type_url"],
             output_type_url=item["output_type_url"],
             declared_effects=[pb.EFFECT_CLASS_PURE_COMPUTE],
             streams_progress=item["streams_progress"],
             display_name=item["display_name"])
        encoded=desc.SerializeToString(deterministic=True)
        assert pb.CapabilityDescriptor.FromString(encoded)==desc
        assert desc.declared_effects==[pb.EFFECT_CLASS_PURE_COMPUTE]
    assert all("ssm" not in item["capability_id"] for item in caps)


def test_authenticated_handshake_and_health_only_source_fixture():
    client,server=_client()
    welcome=client.handshake(client_nonce=b"\x33"*32)
    assert welcome["authenticated"] is True
    assert welcome["session_ref"]==SESSION
    assert welcome["core_epoch_ref"]==EPOCH
    assert not welcome["provider_registered"]
    assert not welcome["tool_invocation_authorized"]
    assert not welcome["os_peer_installed_qualified"]
    assert server.proof_verified is True
    health=client.health()
    assert health["module_id"]=="lu.core"
    assert health["status_code"]=="READY"
    assert health["epoch"]==7
    assert health["authenticated_transport_session"]
    assert not health["tool_invocation_authorized"]
    assert server.received==["hello","auth_proof","health"]
    assert not hasattr(client,"invoke")
    assert not hasattr(client,"register")
    client.close()
    with pytest.raises(c.LuClientRefused,match="authenticated session"):
        client.health()


@pytest.mark.parametrize("fault,pattern", [
    ("zero_challenge","weak host challenge"),
    ("challenge_id","host challenge"),
    ("challenge_version","wire version"),
    ("oversize_challenge","frame length"),
    ("unknown_challenge_field","noncanonical"),
    ("bad_server_mac","server-authentication HMAC mismatch"),
    ("welcome_id","welcome version, identity"),
    ("welcome_version","welcome version, identity"),
    ("wrong_session_mac","server-authentication HMAC mismatch"),
])
def test_forged_handshakes_fail_closed(fault,pattern):
    client,_=_client(fault)
    with pytest.raises(c.LuClientRefused,match=pattern):
        client.handshake(client_nonce=b"\x33"*32)
    assert not client.authenticated


@pytest.mark.parametrize("fault,pattern", [
    ("health_session","session mismatch"),
    ("health_id","health request correlation mismatch"),
    ("health_zero_epoch","invalid health report"),
    ("health_wrong_kind","unexpected frame kind"),
    ("health_foreign_module","health responder must be lu.core"),
])
def test_forged_health_report_fails_closed(fault,pattern):
    client,_=_client(fault)
    client.handshake(client_nonce=b"\x33"*32)
    with pytest.raises(c.LuClientRefused,match=pattern):
        client.health()
    assert not client.authenticated, "a rejected health frame poisons the session"


def test_disconnected_core_health_is_not_exchanged_for_execution_authority():
    client, _ = _client("health_disconnected")
    client.handshake(client_nonce=b"\\x33"*32)
    report = client.health()
    assert report["module_id"] == "lu.core"
    assert report["connected"] is False
    assert report["status_code"] == "DOWN"
    assert not report["tool_invocation_authorized"]
    client.close()


def test_handshake_is_one_time_and_replay_does_not_create_second_session():
    client,_=_client()
    client.handshake(client_nonce=b"\x33"*32)
    with pytest.raises(c.LuClientRefused,match="one-time handshake"):
        client.handshake(client_nonce=b"\x44"*32)
    client.close()


def test_unenrolled_keys_and_nonce_refused_before_sending():
    for badkey in (b"\x00"*32,b"k"*31,b"k"*33):
        with pytest.raises(c.LuClientRefused,match="handshake key"):
            c.AuthenticatedReadOnlyLuClient(SyntheticCoreStream(),
                enrolled_key=badkey,installed_package_sha256=PACKAGE)
    with pytest.raises(c.LuClientRefused,match="package SHA-256"):
        c.AuthenticatedReadOnlyLuClient(SyntheticCoreStream(),
            enrolled_key=KEY,installed_package_sha256=b"\x00"*32)
    client,server=_client()
    with pytest.raises(c.LuClientRefused,match="client nonce"):
        client.handshake(client_nonce=b"\x00"*32)
    assert server.received==[]


def test_refuses_oversized_and_truncated_inbound_frame():
    class SimpleReadStream:
        def __init__(self,raw):
            self.raw=raw
        def read(self,n):
            result,self.raw=self.raw[:n],self.raw[n:]
            return result
        def write(self,b):return len(b)
    for payload,pattern in [
        (struct.pack(">I",c.MAX_FRAME+1),"frame length"),
        (b"\x00\x00\x00\x05xx","truncated"),
        (b"\x00\x00\x00\x00","frame length"),
    ]:
        client=c.AuthenticatedReadOnlyLuClient(SimpleReadStream(payload),
                   enrolled_key=KEY,installed_package_sha256=PACKAGE)
        with pytest.raises(c.LuClientRefused,match=pattern):
            client.handshake(client_nonce=b"\x33"*32)


def test_non_protobuf_input_and_unknown_effect_are_not_accepted():
    good=contract.proposal()
    assert len(good["register_workspace"]["capabilities"])==5
    with pytest.raises(ValueError,match="refused"):
        contract.refuse_unsupported_invoke(
           "EFFECT_CLASS_READ_WORKSPACE","cognitum.hdc.query",
           host_pure_bridge=True)
    with pytest.raises(ValueError,match="refused"):
        contract.refuse_unsupported_invoke(
           "EFFECT_CLASS_PURE_COMPUTE","cognitum.hdc.query",
           host_pure_bridge=True)


def test_linux_unix_connect_refuses_untrusted_path_before_socket_open():
    if not __import__("sys").platform.startswith("linux"):
        with pytest.raises(c.LuClientRefused,match="Linux UDS only"):
            c.connect_linux_unix_socket("/unused.sock",expected_uid=0)
        return
    with pytest.raises(c.LuClientRefused,match="absolute endpoint"):
        c.connect_linux_unix_socket("../user-supplied.sock",expected_uid=0)
    with pytest.raises(c.LuClientRefused,match="service UID"):
        c.connect_linux_unix_socket("/tmp/not-a-real-core.sock",expected_uid=-1)
