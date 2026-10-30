import unittest
from unittest.mock import patch
from cognitum.alpha_native import HostAdmission, make_call, run_once, _parse
from cognitum.proto import alpha_native_pb2 as p
from cognitum.proto.capability_pb2 import CalculateRationalResult

class NativeAlphaTests(unittest.TestCase):
    def gate(self,**kw):
        return HostAdmission('conversation1','r1',frozenset({'calc.rational'}),True,6000,**kw)
    def test_default_deny(self):
        with self.assertRaises(PermissionError):run_once(make_call('r1','1/3'),HostAdmission())
    def test_actual_worker_calculates_binary_protobuf(self):
        raw=run_once(make_call('r1','1/3 + 1/6'),self.gate())
        r=_parse(p.Reply,raw,16384)
        self.assertEqual(r.status,p.Reply.COMPLETED)
        self.assertEqual(CalculateRationalResult.FromString(r.result_payload).value,'1/2')
        self.assertFalse(r.lu_integrated or r.os_isolation_verified)
    def test_request_identity_mismatch(self):
        with self.assertRaisesRegex(PermissionError,'REQUEST_ID_MISMATCH'):
            run_once(make_call('wrong','1'),self.gate())
    def test_operation_not_allowed(self):
        with self.assertRaises(PermissionError):
            run_once(make_call('r1','1'),HostAdmission('conv','r1',frozenset(),True))
    def test_wrong_type(self):
        c=p.Call.FromString(make_call('r1','1'))
        c.request_type_url='type.googleapis.com/evil.Command'
        with self.assertRaisesRegex(ValueError,'TYPE_URL_MISMATCH'):
            run_once(c.SerializeToString(deterministic=True),self.gate())
    def test_unsupported_operation(self):
        c=p.Call.FromString(make_call('r1','1'));c.operation='shell.run'
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_CALL'):
            run_once(c.SerializeToString(deterministic=True),self.gate())
    def test_unknown_field_denied(self):
        with self.assertRaisesRegex(ValueError,'NONCANONICAL'):
            run_once(make_call('r1','1')+b'\x98\x06\x01',self.gate())
    def test_invalid_expression_does_not_spawn(self):
        c=p.Call.FromString(make_call('r1','1'))
        from cognitum.proto.capability_pb2 import CalculateRationalRequest
        c.request_payload=CalculateRationalRequest(expression='__import__("os")').SerializeToString()
        with self.assertRaises(ValueError),patch('cognitum.alpha_native.subprocess.run') as fake:
            run_once(c.SerializeToString(deterministic=True),self.gate())
        fake.assert_not_called()
    def test_bad_timeout(self):
        with self.assertRaises(ValueError):HostAdmission(timeout_ms=7501)
    def test_untrusted_extra_bytes(self):
        from cognitum.alpha_native_worker import serve
        import io,struct
        call=make_call('r1','1')
        self.assertEqual(serve(io.BytesIO(struct.pack('>I',len(call))+call+b'extra'),io.BytesIO()),2)
    def test_timeout_is_reported_without_success(self):
        import subprocess
        with patch('cognitum.alpha_native.subprocess.run', side_effect=subprocess.TimeoutExpired('child',2)):
            with self.assertRaisesRegex(TimeoutError,'ALPHA_WORKER_TIMEOUT'):
                run_once(make_call('r1','1'),self.gate())
    def test_worker_cannot_forge_lu_authority(self):
        import subprocess,struct
        forged=p.Reply(version=1,request_id='r1',status=p.Reply.COMPLETED,
                      lu_integrated=True)
        frame=forged.SerializeToString(deterministic=True)
        fake=subprocess.CompletedProcess([],0,struct.pack('>I',len(frame))+frame,b'')
        with patch('cognitum.alpha_native.subprocess.run',return_value=fake):
            with self.assertRaisesRegex(ValueError,'FORGED_ASSURANCE'):
                run_once(make_call('r1','1'),self.gate())
    def test_no_worker_success_when_truncated(self):
        import subprocess
        fake=subprocess.CompletedProcess([],0,b'\x00\x00\x00\xff',b'')
        with patch('cognitum.alpha_native.subprocess.run',return_value=fake):
            with self.assertRaisesRegex(ValueError,'FRAME_MISMATCH'):
                run_once(make_call('r1','1'),self.gate())
    def test_no_success_when_worker_faults(self):
        with patch('cognitum.alpha_native.subprocess.run') as fake:
            fake.return_value.returncode=1;fake.return_value.stderr=b'';fake.return_value.stdout=b''
            with self.assertRaisesRegex(ValueError,'ALPHA_WORKER_FAILED'):
                run_once(make_call('r1','1'),self.gate())
if __name__=='__main__':unittest.main()
