"""Research-only acceptance for restored lesser-used HDC techniques."""
import unittest
import numpy as np

from cognitum.research.hdc_recovered.models import BSC
from cognitum.research.hdc_recovered.stochastic import StochasticHDC
from cognitum.research.hdc_recovered.lowdisc import LowDiscEncoder
from cognitum.research.hdc_recovered.neuralhd import NeuralHDPipeline
from cognitum.research.hdc_recovered.quantum import QuantumHDC


class RecoveredHdcAdditionalMethods(unittest.TestCase):
    def test_stochastic_bitwise_reference_matches_bsc(self):
        result = StochasticHDC(128, seed=2).validate_equivalence(n=8)
        self.assertTrue(all(result.values()), result)

    def test_low_discrepancy_generators_are_reproducible(self):
        for name in ("iid_indexed", "sobol", "halton"):
            with self.subTest(name=name):
                encoder = LowDiscEncoder(32, method=name, seed=4)
                batch = encoder.generate_batch(8)
                self.assertEqual(batch.shape, (8, 32))
                self.assertTrue(np.array_equal(batch[3], encoder.generate(index=3)))
                self.assertTrue(np.isin(batch, [-1, 1]).all())
                coherence = encoder.orthogonality_check(8)
                self.assertGreaterEqual(coherence["mean_abs_dot_over_D"], 0)
        # Low-discrepancy binarization is NOT assumed superior to IID.

    def test_neuralhd_dimension_reduction_cleans_up_known_source(self):
        model = BSC(128, seed=2)
        matrix = model.atomic(10, np.random.default_rng(2))
        pipeline = NeuralHDPipeline(model, threshold=0.5)
        stats = pipeline.encode_and_reduce(matrix)
        self.assertLessEqual(stats["D_effective"], 128)
        ranked, scores = pipeline.search(matrix[3], k=3)
        self.assertEqual(int(ranked[0]), 3)
        self.assertEqual(len(scores), 3)

    def test_quantum_reference_is_classical_simulation_only(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", np.exceptions.ComplexWarning)
            result = QuantumHDC(64, seed=3).validate_equivalence(n=5)
        self.assertTrue(result["bind_equivalence"])
        self.assertTrue(result["dot_well_defined"])
        self.assertEqual(result["n_qubits"], 6)
        self.assertIn("simulation", result["note"].lower())


if __name__ == "__main__":
    unittest.main()
