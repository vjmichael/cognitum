"""Seven fail-closed, offline C14 G9 source & Protobuf smoke checks."""
from tools import run_c14_p4e_g7_study as g7
from tools import run_c14_p4e_g9_interval_comparison as g9
from cognitum import causal_interval_comparison as wired
from cognitum.proto import causal_interval_comparison_pb2 as pb

def main():
    checks=[]
    x,_=g7.make_fixture('observed_heterogeneous',1001,300)
    b=g9.bootstrap_intervals(x,seed=101,resamples=199)
    checks.append(b['status']=='COMPUTED')
    checks.append(len(b['methods'])==4)
    checks.append(g9.aipw_crossfit(x,seed=101)['status']=='COMPUTED')
    req=pb.IntervalComparisonRequest(schema_version=1,trace_id='smoke',scenario='observed_heterogeneous',seed=1001,sample_size=300,bootstrap_resamples=199,confidence=.95)
    result,receipt=wired.calculate(req)
    checks.append(wired.verify(req,result,receipt))
    result.host_authorized=True
    checks.append(not wired.verify(req,result,receipt))
    rows,_=g7.make_fixture('no_overlap',1001,300)
    checks.append(g9.bootstrap_intervals(rows,seed=101,resamples=199)['status']=='REJECTED_INSUFFICIENT_POSITIVITY')
    report=g9.conduct(seeds=(1001,1002),sizes=(300,),resamples=199)
    checks.append(g9.verify_report(report))
    if not all(checks):raise RuntimeError('G9_SMOKE_FAILED:'+str(checks))
    print(f'PASS: {sum(checks)}/{len(checks)} G9 offline research-only smoke checks')

if __name__=='__main__':main()
