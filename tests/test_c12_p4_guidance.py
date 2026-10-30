"""Focused C12 P4 experimental-guidance functional and adversarial tests."""
import hashlib
import random
import unittest

from cognitum.planning_guidance import (
    artifact_digest, GuidanceRegistry, verify_guided_frame, make_guided_audit, frame,
    guided_capability_manifest, MAX_HINTS,
)
from cognitum.proto import planning_guidance_pb2 as g
from cognitum.proto import planning_pb2 as p
from cognitum.planning import PlanningRegistry


def example():
    base = p.PlanningRequest(schema_version=1, trace_id='p4', engine=p.ASTAR_HMAX, timeout_ms=2000)
    t=base.task
    t.facts.extend(['start','key','goal','trap'])
    t.initial_true.append(0)
    t.goal_true.append(2)
    t.actions.add(id='key', require_true=[0], add=[1], cost=1)
    t.actions.add(id='unlock', require_true=[1], add=[2], cost=1)
    t.actions.add(id='expensive', require_true=[0], add=[2], cost=9)
    t.actions.add(id='trap', require_true=[0], add=[3], cost=1)
    t.actions.add(id='escape', require_true=[3], add=[2], cost=12)
    base.task.max_states=128
    base.task.max_expansions=128
    req = g.GuidedRequest(schema_version=1)
    req.planning.CopyFrom(base)
    a=req.guidance
    a.schema_version=1
    a.backend_id='offline-transition-classifier-v1'
    a.source_reference='doi:10.3233/FAIA251375'
    a.model_sha256=hashlib.sha256(b'synthetic-untrusted-model-id').digest()
    a.hints.add(state_bits=1, action_index=0, label=g.PREDICTED_DEAD_END)
    a.hints.add(state_bits=1, action_index=3, label=g.PREFERRED_TRANSITION)
    sign(req)
    return req


def sign(req):
    req.guidance.content_sha256=artifact_digest(req.guidance)
    return req


def run(req, *, allowed=True, enabled=True, authorized=True):
    return g.GuidedResult.FromString(GuidanceRegistry(enabled=enabled,
        approved_artifact_digests={req.guidance.content_sha256} if allowed else set())
        .solve_frame(frame(req),host_authorized=authorized))


def receipt(req, result, *, pin=True):
    return g.GuidedReceipt.FromString(verify_guided_frame(
        frame(req),frame(result),trusted_artifact_sha256=req.guidance.content_sha256 if pin else None))


class GuidedPlanningTests(unittest.TestCase):
    def test_real_guided_astar_valid_and_optimal(self):
        req=example();out=run(req)
        self.assertEqual(out.status,p.VERIFIED_OPTIMAL)
        self.assertEqual(out.total_cost,2)
        self.assertEqual(list(out.actions),[0,1])
        self.assertGreaterEqual(out.applied_hints,2)
        self.assertTrue(receipt(req,out).optimality_verified)

    def test_advice_never_prunes_predicted_dead_end(self):
        req=example()
        # Malicious predicted-dead-end label on the only affordable path.
        req.guidance.hints[0].label=g.PREDICTED_DEAD_END
        req.guidance.hints[1].label=g.PREDICTED_DEAD_END
        sign(req)
        out=run(req)
        self.assertEqual(out.total_cost,2)
        self.assertEqual(out.status,p.VERIFIED_OPTIMAL)

    def test_tie_breaker_changes_path_not_optimality(self):
        req=example()
        t=req.planning.task
        t.facts.extend(['alternate'])
        t.actions.add(id='alternate_start',require_true=[0],add=[4],cost=1)
        t.actions.add(id='alternate_finish',require_true=[4],add=[2],cost=1)
        req.guidance.hints.add(state_bits=1,action_index=5,label=g.PREFERRED_TRANSITION)
        req.guidance.hints[0].label=g.DISFAVORED_TRANSITION
        sign(req)
        out=run(req)
        self.assertEqual(out.status,p.VERIFIED_OPTIMAL)
        self.assertEqual(out.total_cost,2)
        self.assertTrue(receipt(req,out).evidence_valid)

    def test_untrusted_artifact_rejected_by_host(self):
        self.assertEqual(run(example(),allowed=False).reason_code,'GUIDANCE_NOT_HOST_APPROVED')

    def test_disabled_and_authorization_required(self):
        self.assertEqual(run(example(),enabled=False).reason_code,'GUIDED_PLANNING_DISABLED')
        self.assertEqual(run(example(),authorized=False).reason_code,'HOST_AUTHORIZATION_REQUIRED')

    def test_receipt_requires_external_trusted_pin(self):
        req=example();out=run(req)
        self.assertFalse(receipt(req,out,pin=False).evidence_valid)
        self.assertEqual(receipt(req,out,pin=False).reason_code,'UNTRUSTED_GUIDANCE_ARTIFACT')

    def test_artifact_mutation_requires_reapproval(self):
        req=example();allowed=req.guidance.content_sha256
        req.guidance.hints[0].label=g.PREFERRED_TRANSITION
        sign(req)
        out=g.GuidedResult.FromString(GuidanceRegistry(enabled=True,
            approved_artifact_digests={allowed}).solve_frame(frame(req),host_authorized=True))
        self.assertEqual(out.reason_code,'GUIDANCE_NOT_HOST_APPROVED')

    def test_content_digest_mismatch_rejected(self):
        req=example();req.guidance.hints[0].label=g.PREFERRED_TRANSITION
        self.assertEqual(run(req).status,p.REJECTED)

    def test_source_reference_requires_canonical_record(self):
        req=example();req.guidance.source_reference='';sign(req)
        self.assertEqual(run(req).status,p.REJECTED)

    def test_model_hash_shape(self):
        req=example();req.guidance.model_sha256=b'x';sign(req)
        self.assertEqual(run(req).status,p.REJECTED)

    def test_engine_must_be_admissible_baseline(self):
        req=example();req.planning.engine=p.WEIGHTED_ASTAR_HMAX
        self.assertEqual(run(req).status,p.REJECTED)

    def test_duplicate_transition_hint(self):
        req=example();req.guidance.hints.add(state_bits=1,action_index=0,label=g.PREFERRED_TRANSITION)
        sign(req)
        self.assertEqual(run(req).status,p.REJECTED)

    def test_invalid_state_and_action_index(self):
        req=example();req.guidance.hints[0].state_bits=255;sign(req)
        self.assertEqual(run(req).status,p.REJECTED)
        req=example();req.guidance.hints[0].action_index=222;sign(req)
        self.assertEqual(run(req).status,p.REJECTED)

    def test_unspecified_hint_label(self):
        req=example();req.guidance.hints[0].label=g.GUIDANCE_UNSPECIFIED;sign(req)
        self.assertEqual(run(req).status,p.REJECTED)

    def test_excess_hints_denied(self):
        req=example()
        for _ in range(MAX_HINTS):
            req.guidance.hints.add(state_bits=0,action_index=1,label=g.PREFERRED_TRANSITION)
        sign(req)
        self.assertEqual(run(req).status,p.REJECTED)

    def test_request_result_binding(self):
        req=example();out=run(req)
        req.planning.task.actions[0].cost=2
        self.assertFalse(receipt(req,out).evidence_valid)

    def test_forged_optimality_and_wrong_reason(self):
        req=example();out=run(req)
        out.actions[:]=[2];out.total_cost=9
        self.assertFalse(receipt(req,out).evidence_valid)
        out=run(req);out.reason_code='SOLVER_SAID_OPTIMAL'
        self.assertFalse(receipt(req,out).evidence_valid)
        out=run(req);out.optimality_verified=False
        self.assertFalse(receipt(req,out).evidence_valid)

    def test_forged_execution_metadata(self):
        req=example();out=run(req)
        out.backend_id='unapproved'
        self.assertFalse(receipt(req,out).evidence_valid)
        out=run(req);out.applied_hints=1_000_000
        self.assertFalse(receipt(req,out).evidence_valid)
        out=run(req);out.host_approved=True
        self.assertFalse(receipt(req,out).evidence_valid)

    def test_malformed_unknown_field_rejected(self):
        req=example();raw=frame(req)+b'\xc0\x0c\x01'
        out=g.GuidedResult.FromString(GuidanceRegistry(enabled=True,
            approved_artifact_digests={req.guidance.content_sha256})
            .solve_frame(raw,host_authorized=True))
        self.assertEqual(out.status,p.REJECTED)

    def test_budget_exhaustion_is_unknown(self):
        req=example();req.planning.task.max_expansions=1
        out=run(req)
        self.assertEqual(out.status,p.UNKNOWN)
        self.assertFalse(out.optimality_verified)
        self.assertFalse(receipt(req,out).optimality_verified)
        self.assertFalse(receipt(req,out).evidence_valid)

    def test_no_solution_independent_unreachable_proof(self):
        req=example();del req.planning.task.actions[1:]
        del req.guidance.hints[:]
        sign(req)
        out=run(req)
        self.assertEqual(out.status,p.VERIFIED_UNREACHABLE)
        self.assertTrue(receipt(req,out).optimality_verified)

    def test_audit_has_no_task_facts_or_model_weights(self):
        req=example();out=run(req)
        audit=g.GuidedAudit.FromString(make_guided_audit(frame(req),frame(out),
            trusted_artifact_sha256=req.guidance.content_sha256))
        self.assertTrue(audit.evidence_valid)
        self.assertTrue(audit.optimality_verified)
        self.assertNotIn(b'start',frame(audit))
        self.assertNotIn(req.guidance.source_reference.encode(),frame(audit))

    def test_manifest_does_not_claim_learned_models_installed(self):
        rows=guided_capability_manifest()
        self.assertTrue(rows[0]['available'])
        self.assertTrue(all(not x['learned_model_executed'] for x in rows))
        self.assertTrue(all(not x['available'] for x in rows[1:]))

    def test_36_seeded_small_cases_against_mature_dijkstra(self):
        for seed in range(36):
            rng=random.Random(seed)
            req=example()
            # Perturb costs and predicted priorities; never change the true goal.
            for a in req.planning.task.actions:
                a.cost=rng.randint(1,12)
            for hint in req.guidance.hints:
                hint.label=rng.choice((g.PREFERRED_TRANSITION,g.DISFAVORED_TRANSITION,g.PREDICTED_DEAD_END))
            sign(req)
            guided=run(req)
            baseline=p.PlanningRequest();baseline.CopyFrom(req.planning)
            baseline.engine=p.NETWORKX_DIJKSTRA
            trusted=p.PlanningResult.FromString(PlanningRegistry(enabled=True).solve_frame(
                frame(baseline),host_authorized=True))
            self.assertEqual(guided.status,p.VERIFIED_OPTIMAL,seed)
            self.assertEqual(trusted.status,p.VERIFIED_OPTIMAL,seed)
            self.assertEqual(guided.total_cost,trusted.total_cost,seed)
            self.assertTrue(receipt(req,guided).optimality_verified)


if __name__ == '__main__':unittest.main()
