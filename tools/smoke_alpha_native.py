"""Run a single explicit local developer smoke. Does not authenticate Lu grants."""
import json
import sys
from cognitum.alpha_native import HostAdmission, make_call, run_once
from cognitum.proto import alpha_native_pb2, capability_pb2

def main():
    gate=HostAdmission('developer-smoke','test1',frozenset({'calc.rational'}),True,7000)
    wire=run_once(make_call('test1','1/3+1/6'),gate)
    reply=alpha_native_pb2.Reply.FromString(wire)
    answer=capability_pb2.CalculateRationalResult.FromString(reply.result_payload)
    outcome={'status':'STANDALONE_BINARY_PROTO_PROCESS_SMOKE_PASS_UNATTESTED',
        'value':answer.value,'lu_integrated':False,'os_sandbox_verified':False,
        'host_authority_authenticated':False,'model_tool_advertised':False}
    print(json.dumps(outcome,sort_keys=True))
    return int(answer.value!='1/2')

if __name__=='__main__':sys.exit(main())
