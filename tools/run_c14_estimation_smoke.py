"""C14 P2A headless mathematical smoke checks, no network/host actions."""
from tests.test_c14_estimation import request, go
from cognitum.causal_estimation import verify_estimation_result
from cognitum.proto import causal_estimation_pb2 as q


def main():
    frame,result,reply=go(request())
    assert result.status==q.ADJUSTED_EFFECT_COMPUTED and result.estimate=='3/5'
    assert verify_estimation_result(frame,reply)
    print('PASS: empirical standardized backdoor adjustment')
    r=request();r.identification.adjustment.clear()
    assert go(r)[1].status==q.ADJUSTMENT_NOT_CERTIFIED
    print('PASS: graph criterion fail-closed')
    r=request();del r.observations[2]
    assert go(r)[1].status==q.POSITIVITY_NOT_MET
    print('PASS: empirical overlap insufficiency')
    r=request();r.backend=q.DOWHY_OPTIONAL_WORKER
    assert go(r)[1].status==q.ESTIMATION_BACKEND_UNAVAILABLE
    print('PASS: unavailable mature backend is not emulated')
    assert go(request(),authorized=False)[1].status==q.ESTIMATION_REJECTED
    print('PASS: host flag denial')
    result.estimate='2/5'
    assert not verify_estimation_result(frame,result.SerializeToString(deterministic=True))
    print('PASS: independent result forgery rejection')

if __name__=='__main__':main()
