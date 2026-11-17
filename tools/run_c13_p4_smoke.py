"""C13 P4 functionality-only smoke: real SciPy conjugate families + real ArviZ."""
import random
from cognitum.probability_conjugate import run_conjugate_frame, verify_conjugate_receipt, make_conjugate_audit
from cognitum.probability_diagnostics import run_diagnostics_frame,verify_diagnostics_receipt
from cognitum.proto import probability_conjugate_pb2 as p, probability_diagnostics_pb2 as d
from tests.test_c13_p4_conjugate import make


def check(condition, label):
    if not condition:raise AssertionError(label)
    print('PASS:',label)


def main():
    for family in ('beta_binomial','gamma_poisson','normal_inverse_gamma'):
        req=make(family)
        raw=req.SerializeToString(deterministic=True)
        out=run_conjugate_frame(raw,host_authorized=True,enabled=True)
        check(p.ConjugateResult.FromString(out).status==p.CONJUGATE_SUCCESS and
              verify_conjugate_receipt(raw,out).evidence_valid,family+' posterior/predictive and cross-check')
    req=make('normal_inverse_gamma');req.normal_inverse_gamma.ClearField('observations');req.normal_inverse_gamma.prior_alpha=.25
    raw=req.SerializeToString(deterministic=True)
    r=p.ConjugateResult.FromString(run_conjugate_frame(raw,host_authorized=True,enabled=True))
    check(r.status==p.CONJUGATE_SUCCESS and not r.posterior_mean_defined and not r.predictive_variance_defined,
          'undefined Student-t moments explicit')
    rng=random.Random(19)
    q=d.DiagnosticsRequest(schema_version=1,trace_id='c13.p4.smoke',timeout_ms=20000)
    x=q.parameters.add(parameter='mu')
    for _ in range(4):x.chains.add().values.extend(rng.gauss(0,1) for _ in range(90))
    raw=q.SerializeToString(deterministic=True)
    out=run_diagnostics_frame(raw,host_authorized=True,enabled=True)
    check(d.DiagnosticsResult.FromString(out).status==d.DIAGNOSTICS_SUCCESS and
          verify_diagnostics_receipt(raw,out).evidence_valid,'real ArviZ Rhat, bulk/tail ESS, MCSE')
    req=make();raw=req.SerializeToString(deterministic=True)
    out=run_conjugate_frame(raw,host_authorized=False,enabled=True)
    check(p.ConjugateResult.FromString(out).status==p.CONJUGATE_REJECTED and not
          verify_conjugate_receipt(raw,out).evidence_valid,'host gate and no forged assurance')
    return 0

if __name__=='__main__':raise SystemExit(main())
