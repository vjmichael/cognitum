"""C13 P3 bounded functionality-only smoke, no comparative benchmark."""
from tests.test_c13_p3_continuous import request, execute
from cognitum import probability_continuous as c
from cognitum.proto import probability_continuous_pb2 as p

def check(cond,label):
    if not cond: raise AssertionError(label)
    print('PASS:',label)

def main():
    raw,out,res=execute()
    check(res.status==p.CONTINUOUS_SUCCESS and c.verify_continuous_receipt(raw,out).analytic_reference_checked,'independently checked analytic hierarchical posterior')
    check(res.moments[1].mean>res.moments[2].mean>0,'partial pooling with observed and unobserved group')
    check(res.moments[1].predictive_sd>res.moments[1].sd,'posterior predictive includes future observation variance')
    check(c.make_continuous_audit(raw,out).exact_gaussian_reference,'privacy-minimized audit receipt')
    check(execute(authorized=False)[2].status==p.CONTINUOUS_REJECTED,'host permission gate')
    check(execute(request(p.PYMC_NUTS))[2].reason_code=='PYMC_WORKER_DISABLED','experimental backend default disabled')
    return 0

if __name__=='__main__':raise SystemExit(main())
