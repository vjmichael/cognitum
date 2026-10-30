"""G5 optional source-runtime smoke; never attests real Lu host isolation."""
from importlib.metadata import version, PackageNotFoundError
from cognitum.causal_mature_backend import run_mature_frame, verify_mature_receipt
from cognitum.proto import causal_mature_pb2 as m
from tests.test_c14_p3c_mature_adapter import fixtures, policy, encode


def main():
    for req in fixtures():
        pkg,pin=('econml','0.17.0') if req.backend==m.ECONML_LINEAR_DML_0170 else ('causal-learn','0.1.4.8')
        try: ready=version(pkg)==pin
        except PackageNotFoundError: ready=False
        if not ready:
            print('SKIP: real',pkg,pin,'not installed')
            continue
        raw=encode(req)
        denied=m.MatureCausalResult.FromString(run_mature_frame(raw))
        assert denied.reason_code=='HOST_AUTHORIZATION_REQUIRED'
        reply=run_mature_frame(raw,host_authorized=True,enabled=True,worker_policy=policy(req.backend))
        got=m.MatureCausalResult.FromString(reply)
        assert got.status==m.MATURE_RESULT_CANDIDATE,got.reason_code
        assert verify_mature_receipt(raw,reply).request_bound_structure_checked
        assert not got.causal_assumptions_verified and not got.orientations_published
        print('PASS:',pkg,pin, 'native Protobuf worker,',got.sample_count,'observations,',
              len(got.effects),'subgroup effects,',len(got.skeleton_edges),'skeleton edges')

if __name__=='__main__':main()
