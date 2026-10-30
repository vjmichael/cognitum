"""C15 T2 P2P offline demonstration using a MOCK host lease (not credentials).

Run: PYTHONPATH=. python tools/run_c15_p2p_t2_c07_demo.py [--out PATH]
No ANSF connection, Lu host, Windows permissions, live source or canonical writes.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from tools.run_c15_p2o_t2_reconciliation import fixture
from cognitum import spatial_structural_c07_bridge as bridge
from cognitum.proto import spatial_structural_c07_bridge_pb2 as pb
from cognitum.proto import state_pb2 as state


class MockOfflineLease:
    """Test only. NEVER pass a lease from model/tool/plugin code in production."""
    def ensure_active(self):return True
    def admit_event(self,scope,event):return scope=='replayDemo'
    def verify_source(self,scope,source,current):
        return scope=='replayDemo' and source.session_id == 'replayDemo'
    def bind_structural_event(self,scope,t2,c07):
        return scope=='replayDemo' and t2.event_id==c07.event_id


def demo():
    original=fixture()
    req=pb.T2C07BridgeRequest(schema_version=1,structural_request=original,research_only=True)
    prior={}
    for i,t2 in enumerate(original.events):
        claim_id=bridge._claim_id(t2)
        op=t2.WhichOneof('change')
        if op=='retract':
            value=prior[claim_id]
            action=state.RETRACT;revision=1
        else:
            value=bridge._digest(bridge._payload(t2)).hex()
            prior[claim_id]=value
            action=state.ASSERT;revision=0
        event=state.StateEvent(
            schema_version=1,event_id=t2.event_id,scope_id='replayDemo',
            claim_id=claim_id,subject_id=t2.candidate_id,predicate=bridge.PREFIX+claim_id,
            value_kind=state.TEXT,value_text=value,origin=state.MODEL_HYPOTHESIS,
            action=action,expected_revision=revision,
            recorded_at_ms=1000*(i+1),effective_at_ms=1000*(i+1),
            source=state.SourceEvidence(session_id='replayDemo',root_entry_id=str(i+1),
              revision_entry_id=str(i+1),content_sha256=sha256(t2.SerializeToString(deterministic=True)).hexdigest(),
              snapshot_id=f'fixture{i+1}'))
        req.c07_event_frames.append(event.SerializeToString(deterministic=True))
    raw=bridge.publish_host_fenced(req,MockOfflineLease(),lambda data:data)
    result=pb.T2C07BridgeResult.FromString(raw)
    return {'phase':'C15 T2 P2P',
      'source':'Synthetic P2O fixture plus synthetic C07 canonical events',
      'security':'Mock-only host lease; NOT source-authenticated or a real Lu security check',
      'result':MessageToDict(result,preserving_proto_field_name=True),
      'no_authority_grant':True,'canonical_writes':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path)
    args=p.parse_args()
    value=json.dumps(demo(),sort_keys=True,indent=2)+'\n'
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(value,encoding='utf-8')
    else:print(value,end='')

if __name__=='__main__':main()
