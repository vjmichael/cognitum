"""Root-trusted export of public signature evidence ONLY; never archives keys."""
from __future__ import annotations
import argparse,base64,hashlib,json,pathlib,sys
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from coordinator_m11 import Lab,ROOT
import m10_durable_auditor as m10
from public_audit_m11 import verify

def export(path,out):
    lab=Lab(path)
    state=lab.reconcile()
    _,fp=m10.load_public(lab.pub)
    man=m10.manifest(lab.caseorder,ROOT,fp)
    anchor=json.loads((lab.anchor/'anchor-state.json').read_text())
    # Drop the host-private verifier public-key PATH from a portable chain;
    # its public fingerprint is independently pinned inside every state.
    anchor.pop('verifier_public_path',None)
    doc={'protocol':'CH40M11-PUBLIC-EVIDENCE-V1','scientific_release':'NO_GO',
         'verifier_public_b64':base64.b64encode(lab.pub.read_bytes()).decode('ascii'),
         'anchor_public_b64':base64.b64encode((lab.anchor/'anchor-public.key').read_bytes()).decode('ascii'),
         'm10_manifest':man,
         'checkpoint_rows':[{k:r[k] for k in ('body_b64','body_sha','signature_b64','tip')} for r in lab.dbrows()],
         'anchor':anchor}
    result=verify(doc,expected_anchor_tip=state['anchor_tip'])
    pathlib.Path(out).write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--lab',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    print('M11_EXPORTED '+json.dumps(export(a.lab,a.out),sort_keys=True))
