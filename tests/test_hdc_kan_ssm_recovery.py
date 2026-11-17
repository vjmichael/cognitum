"""Recovered HDC/KAN/SSM breadth acceptance; no comparative superiority claim."""
import unittest
import numpy as np
from cognitum.research.hdc_recovered.models import MODEL_REGISTRY
from cognitum.research.hdc_recovered.memory import Bank
from cognitum.research.hdc_recovered.sdm import SDM
from cognitum.research.hdc_recovered.resonator import factor_pair_search
from cognitum.research.ssm_recovered import DiagonalSSM
from tests.test_research_optional import kan_artifact
from cognitum.research.kan_optional import _load


class RecoveredHdcFamily(unittest.TestCase):
    def test_binding_unbinding_four_families(self):
        for family in ("bsc", "map", "fhrr", "hrr"):
            with self.subTest(family=family):
                model = MODEL_REGISTRY[family](256, seed=9)
                rng = np.random.default_rng(31)
                a, b = model.atomic(2, rng)
                result = model.unbind(a, model.bind(a, b))
                score = model.similarity(b, result)
                self.assertGreater(score, 0.5)
                if family in ("bsc", "map"):
                    self.assertTrue(np.array_equal(result, b))
                self.assertEqual(model.bundle(model.atomic(3, rng)).shape, (256,))

    def test_cleanup_recovers_exact_item(self):
        for family in MODEL_REGISTRY:
            with self.subTest(family=family):
                model = MODEL_REGISTRY[family](256, seed=11)
                rows = model.atomic(6, np.random.default_rng(44))
                bank = Bank(model, rows, list(range(6)))
                self.assertEqual(bank.cleanup(rows[4]), 4)

    def test_sparse_distributed_memory_and_three_factor_cleanup(self):
        for family in ("bsc", "map"):
            with self.subTest(family=family):
                model = MODEL_REGISTRY[family](256, seed=10)
                rows = model.atomic(5, np.random.default_rng(8))
                mem = SDM(model, 256, n_locations=12, seed=1)
                mem.write(rows[0], rows[1])
                recovered, confidence = mem.lookup(rows[0])
                self.assertTrue(np.array_equal(recovered, rows[1]))
                self.assertGreaterEqual(confidence, 0.99)
                combined = model.bind(model.bind(rows[0], rows[1]), rows[2])
                factors, score = factor_pair_search(model, combined, rows)
                self.assertEqual(factors, [0, 1, 2])
                self.assertGreater(score, 0.99)


class RecoveredKanSsm(unittest.TestCase):
    def test_existing_kan_portable_checkpoint(self):
        model = _load(kan_artifact())
        out = model(np.asarray([[0.0]], dtype=np.float32))
        self.assertEqual(out.shape, (1, 1))
        self.assertTrue(np.isfinite(out).all())

    def test_ssm_independent_numpy_recurrence_and_chunk_restart(self):
        p = {
            "a": [0.75, 0.4],
            "b": [[1.0], [0.25]],
            "c": [[0.5, 1.0]],
            "d": [[0.125]],
        }
        model = DiagonalSSM.from_mapping(p)
        inputs = [[0.1], [0.5], [0.0], [-0.3], [0.8]]
        observed = model.scan(inputs)
        state = np.zeros(2)
        expected = []
        A = np.diag(p["a"])
        B = np.asarray(p["b"])
        C = np.asarray(p["c"])
        D = np.asarray(p["d"])
        for sample in inputs:
            x = np.asarray(sample)
            state = A @ state + B @ x
            expected.append((C @ state + D @ x).tolist())
        np.testing.assert_allclose(observed["outputs"], expected, atol=1e-12, rtol=0)
        first = model.scan(inputs[:2])
        second = model.scan(inputs[2:], first["final_state"])
        np.testing.assert_allclose(first["outputs"] + second["outputs"], observed["outputs"], atol=1e-12, rtol=0)
        self.assertIn("NOT_TRAINED", observed["limitation"])


if __name__ == "__main__":
    unittest.main()
