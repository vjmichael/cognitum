"""C15 T2/T3 P2G: independently computed graph, geometry, and probability oracles.

Only research references. No sensors, Lu, external action, or production calibration.
SciPy/NumPy/NetworkX are REQUIRED for this test module, never silently skipped.
"""
from __future__ import annotations
import math
import random
import unittest
from fractions import Fraction

import networkx as nx
import numpy as np
from scipy.special import expit, logsumexp
from scipy.spatial.transform import Rotation

from cognitum.spatial_ray_occupancy import _dda, integrate as ray_integrate
from cognitum.spatial_temporal_occupancy import integrate as temporal_integrate, _rotate
from cognitum.spatial_assembly import analyze as assembly_analyze, AssemblyRejected
from cognitum.spatial_structural_hypotheses import analyze as hypotheses_analyze
from cognitum.proto import ray_occupancy_pb2 as rp, temporal_occupancy_pb2 as tp
from cognitum.proto import assembly_pb2 as ap, structural_hypotheses_pb2 as hp


def oracle_voxels(start, end, resolution=1, include_endpoint_cell=True):
    """Segment/voxel reference via exact plane intersections and interval midpoints.

    Not DDA: use rational arithmetic and discover all subdivision parameters.
    Positive-length intervals count; endpoint is assigned via floor for hit policy.
    """
    a = tuple(Fraction(str(x)) / resolution for x in start)
    b = tuple(Fraction(str(x)) / resolution for x in end)
    breaks = {Fraction(0), Fraction(1)}
    for i in range(3):
        lo, hi = sorted((a[i], b[i]))
        if a[i] == b[i]:
            continue
        for plane in range(math.floor(lo), math.ceil(hi) + 1):
            u = (plane - a[i]) / (b[i] - a[i])
            if 0 < u < 1:
                breaks.add(u)
    times = sorted(breaks)
    result = []
    for left, right in zip(times, times[1:]):
        t = (left + right) / 2
        cell = tuple(math.floor(a[i] + t * (b[i] - a[i])) for i in range(3))
        if not result or cell != result[-1]:
            result.append(cell)
    endpoint = tuple(math.floor(x) for x in b)
    if include_endpoint_cell and (not result or result[-1] != endpoint):
        result.append(endpoint)
    return result


def batch_ray(start, end, hit=True):
    req = rp.RayBatch(schema_version=1, volume_id='P2G', conversation_id='test', voxel_size_m=1,
                      max_axis=8, research_only=True)
    ray = req.rays.add(source_ref='camera', tick=1, endpoint_hit=hit,
                       hit_probability=.8, free_probability=.3)
    ray.start.x, ray.start.y, ray.start.z = start
    ray.end.x, ray.end.y, ray.end.z = end
    return req


class IndependentP2GTests(unittest.TestCase):
    def test_negative_grid_plane_departure_does_not_mark_zero_length_cell(self):
        a, b = (2., .5, .5), (1.5, .5, .5)
        expected = oracle_voxels(a, b)
        self.assertEqual(expected, [(1, 0, 0)])
        self.assertEqual(_dda(a, b, 1, 8), expected)
        output = ray_integrate(batch_ray(a, b))
        self.assertEqual([(v.x, v.y, v.z) for v in output.cells], expected)
        self.assertEqual(output.cells[0].hit_count, 1)

    def test_negative_grid_corner_departure_excludes_touched_neighbors(self):
        a, b = (2., 2., 2.), (1.5, 1.5, 1.5)
        self.assertEqual(_dda(a, b, 1, 8), oracle_voxels(a, b))
        self.assertEqual(_dda(a, b, 1, 8), [(1, 1, 1)])

    def test_positive_grid_plane_departure_remains_half_open(self):
        self.assertEqual(_dda((2., .5, .5), (2.5, .5, .5), 1, 8), [(2, 0, 0)])

    def test_near_boundary_is_not_snapped_to_boundary(self):
        x = 2 - 2**-30
        result = _dda((x, .5, .5), (2.5, .5, .5), 1, 8)
        self.assertEqual(result, [(1, 0, 0), (2, 0, 0)])

    def test_no_hit_endpoint_boundary_is_not_false_free_cell(self):
        a, b = (.5, .5, .5), (2., .5, .5)
        expected = oracle_voxels(a, b, include_endpoint_cell=False)
        self.assertEqual(expected, [(0, 0, 0), (1, 0, 0)])
        self.assertEqual(_dda(a, b, 1, 8, include_endpoint_cell=False), expected)
        result = ray_integrate(batch_ray(a, b, hit=False))
        self.assertEqual([(v.x, v.y, v.z) for v in result.cells], expected)
        self.assertTrue(all(v.free_count == 1 for v in result.cells))

    def test_endpoint_boundary_assigned_to_endpoint_cell(self):
        a, b = (.5, .5, .5), (2., .5, .5)
        self.assertEqual(_dda(a, b, 1, 8), oracle_voxels(a, b))
        self.assertEqual(_dda(a, b, 1, 8), [(0, 0, 0), (1, 0, 0), (2, 0, 0)])

    def test_exact_interval_oracle_240_seeded_segments(self):
        rng = random.Random(1515007)
        values = [i/4 for i in range(1, 32)]  # quarter voxels and exact planes
        for k in range(240):
            a = tuple(rng.choice(values) for _ in range(3))
            b = tuple(rng.choice(values) for _ in range(3))
            if a == b:
                continue
            with self.subTest(case=k, start=a, end=b):
                self.assertEqual(_dda(a, b, 1, 8), oracle_voxels(a, b))

    def test_multi_parent_assembly_dag_vs_networkx_96_cases(self):
        rng = random.Random(1515011)
        for k in range(96):
            count = rng.randint(4, 15)
            req = ap.AssemblyResearchRequest(schema_version=1, graph_id='parity',
                                             conversation_id='test', research_only=True)
            graph = nx.DiGraph()
            for i in range(count):
                name = f'o{i}'
                graph.add_node(name)
                req.objects.add(id=name, kind='part', source_ref='fixture', evidence=ap.ASSEMBLY_OBSERVED)
            pairs = [(a, b) for a in range(count) for b in range(count) if a != b]
            rng.shuffle(pairs)
            for a, b in pairs[:rng.randint(count//2, count * 2)]:
                req.memberships.add(part_id=f'o{a}', assembly_id=f'o{b}',role='member',
                                    source_ref='fixture',evidence=ap.ASSEMBLY_OBSERVED)
                graph.add_edge(f'o{a}', f'o{b}')
            expected_dag = nx.is_directed_acyclic_graph(graph)
            with self.subTest(case=k, dag=expected_dag):
                if expected_dag:
                    result = assembly_analyze(req)
                    self.assertFalse(result.grants_authority)
                    # The graph can be multi-parent. Role counts are distinct per assembly.
                    for row in result.roles:
                        expected = len({x.part_id for x in req.memberships
                                        if x.assembly_id == row.assembly_id and x.role == row.role})
                        self.assertEqual(row.claimed_count, expected)
                else:
                    with self.assertRaisesRegex(AssemblyRejected, 'PART_WHOLE_CYCLE'):
                        assembly_analyze(req)

    def test_structural_hypothesis_posterior_vs_scipy_64_cases(self):
        rng = random.Random(1515012)
        for k in range(64):
            req = hp.StructuralHypothesisRequest(schema_version=1, graph_id='parity',
                                                  conversation_id='test', research_only=True)
            priors = [rng.uniform(.01, 10) for _ in range(3)]
            for i in range(3):
                h = req.hypotheses.add(hypothesis_id=f'h{i}',prior_weight=priors[i])
                h.assertions.add(assembly_id='item',part_id=f'part{i}',role='component',present=True)
            logprob = np.log(priors)
            for t in range(12):
                observation = req.observations.add(source_ref=f's{t}',tick=t+1)
                likelihoods = [rng.uniform(.00001, 1) for _ in range(3)]
                logprob += np.log(likelihoods)
                for i in range(3):
                    observation.likelihoods.add(hypothesis_id=f'h{i}',likelihood=likelihoods[i])
            expected = np.exp(logprob - logsumexp(logprob))
            result = hypotheses_analyze(req)
            actual = {r.hypothesis_id: r.relative_weight for r in result.ranked}
            with self.subTest(case=k):
                for i in range(3):
                    self.assertAlmostEqual(actual[f'h{i}'], expected[i], delta=2e-12)
                self.assertAlmostEqual(sum(actual.values()), 1., delta=1e-12)
                self.assertFalse(result.grants_authority)

    def test_scipy_quaternion_reference_96_seeded_rotations(self):
        rng = np.random.default_rng(1515013)
        for k in range(96):
            q = Rotation.random(random_state=rng).as_quat()  # xyzw
            v = rng.normal(size=3)
            expected = Rotation.from_quat(q).apply(v)
            actual = _rotate((q[3], q[0], q[1], q[2]), tuple(v))
            with self.subTest(case=k):
                np.testing.assert_allclose(actual, expected, rtol=0, atol=2e-12)

    def test_independent_temporal_logodds_and_scipy_sigmoid(self):
        req = tp.TemporalOccupancyRequest(schema_version=1, conversation_id='test',
              volume_id='parity', voxel_size_m=1, max_axis=8,evaluation_tick=12,
              half_life_ticks=4,research_only=True)
        f = req.frames.add(frame_id='world',qw=1)
        f.translation.x=f.translation.y=f.translation.z=0
        for src, tick, hit, hp_, fp_ in [('a',12,True,.8,.2),('b',8,False,.7,.25),('c',4,True,.6,.1)]:
            ray = req.rays.add(source_ref=src,tick=tick,frame_id='world',endpoint_hit=hit,
                               hit_probability=hp_,free_probability=fp_)
            ray.start.x=.25;ray.start.y=.25;ray.start.z=.25
            ray.end.x=.75;ray.end.y=.25;ray.end.z=.25
        result = temporal_integrate(req)
        self.assertEqual(len(result.cells), 1)
        lod = (math.log(.8/.2)*1 + math.log(.25/.75)*.5 + math.log(.6/.4)*.25)
        self.assertAlmostEqual(result.cells[0].log_odds, lod, places=12)
        self.assertAlmostEqual(result.cells[0].probability, expit(lod), places=12)
        self.assertTrue(result.cells[0].conflicted)
        self.assertFalse(result.grants_authority)

    def test_no_hit_temporal_endpoint_does_not_emit_false_free_voxel(self):
        req = tp.TemporalOccupancyRequest(schema_version=1,conversation_id='test',
             volume_id='parity',voxel_size_m=1,max_axis=8,evaluation_tick=1,
             half_life_ticks=3,research_only=True)
        f = req.frames.add(frame_id='world',qw=1)
        f.translation.x=f.translation.y=f.translation.z=0
        r = req.rays.add(source_ref='camera',tick=1,frame_id='world',endpoint_hit=False,
                         hit_probability=.8,free_probability=.3)
        r.start.x=.5;r.start.y=r.start.z=.5
        r.end.x=2;r.end.y=r.end.z=.5
        cells = temporal_integrate(req).cells
        self.assertEqual([(v.x,v.y,v.z) for v in cells], [(0,0,0),(1,0,0)])
        self.assertTrue(all(v.free_count == 1 for v in cells))

    def test_negative_boundary_temporal_ray_uses_correct_start_cell(self):
        req = tp.TemporalOccupancyRequest(schema_version=1,conversation_id='test',
              volume_id='parity',voxel_size_m=1,max_axis=8,evaluation_tick=1,
              half_life_ticks=3,research_only=True)
        f = req.frames.add(frame_id='world',qw=1)
        f.translation.x=f.translation.y=f.translation.z=0
        r = req.rays.add(source_ref='camera',tick=1,frame_id='world',endpoint_hit=True,
                         hit_probability=.8,free_probability=.3)
        r.start.x=2;r.start.y=r.start.z=.5
        r.end.x=1.5;r.end.y=r.end.z=.5
        cells = temporal_integrate(req).cells
        self.assertEqual([(v.x,v.y,v.z) for v in cells], [(1,0,0)])
        self.assertEqual(cells[0].hit_count,1)

if __name__ == '__main__':
    unittest.main()
