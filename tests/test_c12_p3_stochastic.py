"""Bounded functionality/assurance tests; no throughput or model benchmark."""
import unittest
from fractions import Fraction
from cognitum.proto import planning_stochastic_pb2 as p
from cognitum.planning_stochastic import run, verify, audit, manifest, _decode


def example(method=p.FINITE_HORIZON_BELLMAN, simulations=0):
    req = p.StochasticRequest(schema_version=1, trace_id='p3-check', method=method,
                              simulations=simulations, random_seed=42, timeout_ms=3000)
    req.model.state_names.extend(['start','safe','jackpot'])
    req.model.terminal_reward_milli.extend([0, 500, 2000])
    req.model.horizon = 3
    req.model.discount_ppm = 1_000_000
    # Safe action deterministic; risk can be worth taking depending on horizon.
    req.model.decisions.add(state=0, action_id='safe').outcomes.add(next_state=1, probability_ppm=1_000_000, reward_milli=0)
    risk = req.model.decisions.add(state=0, action_id='risk')
    risk.outcomes.add(next_state=2, probability_ppm=250_000, reward_milli=0)
    risk.outcomes.add(next_state=0, probability_ppm=750_000, reward_milli=-200)
    req.model.decisions.add(state=1, action_id='stay').outcomes.add(next_state=1, probability_ppm=1_000_000, reward_milli=30)
    req.model.decisions.add(state=2, action_id='stay').outcomes.add(next_state=2, probability_ppm=1_000_000, reward_milli=30)
    return req


def compute(req, **kwargs):
    return p.StochasticResult.FromString(run(req.SerializeToString(deterministic=True),
                                              enabled=True, host_authorized=True, **kwargs))


def checked(req, result):
    return verify(req.SerializeToString(deterministic=True), result.SerializeToString(deterministic=True))


class StochasticPlanningTests(unittest.TestCase):
    def test_exact_policy(self):
        q=example();r=compute(q)
        self.assertEqual(r.status,p.VERIFIED_POLICY)
        self.assertTrue(r.optimality_verified)
        self.assertTrue(checked(q,r).evidence_valid)
        self.assertEqual(len(r.policy),q.model.horizon*len(q.model.state_names))

    def test_fractional_value(self):
        q=example();r=compute(q)
        self.assertTrue(any(Fraction(x.expected_value_fraction).denominator>1 for x in r.policy))

    def test_policy_tamper_action(self):
        q=example();r=compute(q)
        original=r.policy[0].action_id
        r.policy[0].action_id='injected'
        self.assertNotEqual(original,r.policy[0].action_id)
        self.assertFalse(checked(q,r).evidence_valid)

    def test_policy_tamper_value(self):
        q=example();r=compute(q)
        r.policy[0].expected_value_fraction='1000000000'
        self.assertFalse(checked(q,r).evidence_valid)

    def test_policy_duplicate_entry(self):
        q=example();r=compute(q)
        r.policy.add().CopyFrom(r.policy[0])
        self.assertFalse(checked(q,r).evidence_valid)

    def test_policy_missing_entry(self):
        q=example();r=compute(q)
        del r.policy[0]
        self.assertFalse(checked(q,r).evidence_valid)

    def test_policy_reject_noncanonical_fraction(self):
        q=example();r=compute(q)
        r.policy[0].expected_value_fraction='2/4'
        self.assertFalse(checked(q,r).evidence_valid)

    def test_policy_false_optimum(self):
        q=example();r=compute(q)
        row=next(x for x in r.policy if x.stage==0 and x.state==0)
        row.action_id='safe' if row.action_id!='safe' else 'risk'
        self.assertFalse(checked(q,r).evidence_valid)

    def test_denied_by_default(self):
        q=example();r=p.StochasticResult.FromString(run(q.SerializeToString()))
        self.assertEqual(r.status,p.REJECTED_STOCHASTIC)

    def test_requires_host(self):
        q=example();r=p.StochasticResult.FromString(run(q.SerializeToString(),enabled=True))
        self.assertEqual(r.reason_code,'HOST_AUTHORIZATION_REQUIRED')

    def test_req_binding(self):
        q=example();r=compute(q);q.model.terminal_reward_milli[2]+=1
        self.assertFalse(checked(q,r).evidence_valid)

    def test_method_tamper(self):
        q=example();r=compute(q);r.method=p.UCT_MCTS
        self.assertFalse(checked(q,r).evidence_valid)

    def test_backend_tamper(self):
        q=example();r=compute(q);r.backend_id='untrusted'
        self.assertFalse(checked(q,r).evidence_valid)

    def test_mcts_estimate_never_optimal(self):
        q=example(p.UCT_MCTS,300);r=compute(q)
        self.assertEqual(r.status,p.ESTIMATED_ACTION)
        self.assertFalse(r.policy_verified)
        self.assertFalse(r.optimality_verified)
        self.assertEqual(sum(v.visits for v in r.root_visits),300)
        self.assertTrue(checked(q,r).evidence_valid)
        self.assertFalse(checked(q,r).optimality_verified)

    def test_mcts_repeatability(self):
        q=example(p.UCT_MCTS,100);r=compute(q);s=compute(q)
        self.assertEqual(r.root_estimated_value,s.root_estimated_value)
        self.assertEqual([(x.action_id,x.visits) for x in r.root_visits],[(x.action_id,x.visits) for x in s.root_visits])

    def test_mcts_tamper_visits(self):
        q=example(p.UCT_MCTS,40);r=compute(q)
        r.root_visits[0].visits+=1
        self.assertFalse(checked(q,r).evidence_valid)

    def test_mcts_tamper_estimate(self):
        q=example(p.UCT_MCTS,40);r=compute(q);r.root_estimated_value='999999'
        self.assertFalse(checked(q,r).evidence_valid)

    def test_mcts_forged_certification(self):
        q=example(p.UCT_MCTS,40);r=compute(q);r.optimality_verified=True
        self.assertFalse(checked(q,r).evidence_valid)

    def test_mcts_reject_zero_simulations(self):
        q=example(p.UCT_MCTS,0)
        self.assertEqual(compute(q).status,p.REJECTED_STOCHASTIC)

    def test_mcts_reject_excessive_simulations(self):
        q=example(p.UCT_MCTS,2001)
        self.assertEqual(compute(q).status,p.REJECTED_STOCHASTIC)

    def test_unormalized_distribution(self):
        q=example();q.model.decisions[1].outcomes[0].probability_ppm=999_999
        self.assertEqual(compute(q).status,p.REJECTED_STOCHASTIC)

    def test_zero_probability_forbidden(self):
        q=example();q.model.decisions[1].outcomes[0].probability_ppm=0
        self.assertEqual(compute(q).status,p.REJECTED_STOCHASTIC)

    def test_state_with_no_legal_action(self):
        q=example();del q.model.decisions[-1]
        self.assertEqual(compute(q).status,p.REJECTED_STOCHASTIC)

    def test_duplicate_state_action(self):
        q=example();q.model.decisions.add().CopyFrom(q.model.decisions[0])
        self.assertEqual(compute(q).status,p.REJECTED_STOCHASTIC)

    def test_unsupported_method(self):
        q=example();q.method=99
        self.assertEqual(compute(q).status,p.REJECTED_STOCHASTIC)

    def test_horizon_zero_forbidden(self):
        q=example();q.model.horizon=0
        self.assertEqual(compute(q).status,p.REJECTED_STOCHASTIC)

    def test_rational_discount(self):
        q=example();q.model.discount_ppm=500_000
        r=compute(q);self.assertTrue(checked(q,r).optimality_verified)

    def test_request_unknown_field_rejected(self):
        q=example();frame=q.SerializeToString(deterministic=True)+b'\xf8\x07\x01'
        r=p.StochasticResult.FromString(run(frame,enabled=True,host_authorized=True))
        self.assertEqual(r.status,p.REJECTED_STOCHASTIC)

    def test_audit_has_no_original_state_names(self):
        q=example();r=compute(q)
        raw=audit(q.SerializeToString(deterministic=True),r.SerializeToString(deterministic=True))
        self.assertNotIn(b'jackpot',raw)
        self.assertTrue(p.StochasticAudit.FromString(raw).evidence_valid)

    def test_manifest_experimental_disabled(self):
        x=manifest()
        self.assertTrue(any(y['maturity']=='research' and not y['available'] for y in x))

    def test_mcts_single_action(self):
        q=example(p.UCT_MCTS,30);del q.model.decisions[1]
        r=compute(q)
        self.assertEqual(r.root_action_id,'safe')
        self.assertTrue(checked(q,r).evidence_valid)

    def test_random_small_models_have_exact_policy(self):
        import random
        rng=random.Random(127)
        for n in range(50):
            q=p.StochasticRequest(schema_version=1,trace_id='property',method=p.FINITE_HORIZON_BELLMAN,timeout_ms=3000)
            size=rng.randint(1,4)
            q.model.state_names.extend('s'+str(i) for i in range(size))
            q.model.terminal_reward_milli.extend(rng.randint(-30,30) for _ in range(size))
            q.model.horizon=rng.randint(1,5);q.model.discount_ppm=rng.randint(1,1_000_000)
            for state in range(size):
                for ai in range(rng.randint(1,3)):
                    d=q.model.decisions.add(state=state,action_id='a'+str(ai))
                    if rng.random()<.5:
                        d.outcomes.add(next_state=rng.randrange(size),probability_ppm=1_000_000,reward_milli=rng.randint(-20,20))
                    else:
                        left=rng.randint(1,999_999)
                        d.outcomes.add(next_state=rng.randrange(size),probability_ppm=left,reward_milli=rng.randint(-20,20))
                        d.outcomes.add(next_state=rng.randrange(size),probability_ppm=1_000_000-left,reward_milli=rng.randint(-20,20))
            r=compute(q)
            self.assertEqual(r.status,p.VERIFIED_POLICY, n)
            self.assertTrue(checked(q,r).optimality_verified,n)


if __name__=='__main__':unittest.main()
