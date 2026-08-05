import unittest

import numpy as np

from benchmarks.network_profiles import estimate_runtime
from benchmarks.run_federated_mnist import dequantize, quantize_distinct
from benchmarks.secure_median import distinct_random_matrix, upper_median


class MedianTests(unittest.TestCase):
    def test_upper_median_matches_paper_rank_for_even_clients(self):
        values = np.array(
            [
                [1, 90],
                [2, 80],
                [3, 70],
                [4, 60],
                [5, 50],
                [6, 40],
                [7, 30],
                [8, 20],
                [9, 10],
                [10, 0],
            ]
        )
        np.testing.assert_array_equal(upper_median(values), [6, 50])

    def test_generated_inputs_are_exact_length_and_unique_per_coordinate(self):
        values = distinct_random_matrix(clients=10, dimension=100, L=16, seed=7)
        self.assertTrue(np.all(values >= 2**15))
        self.assertTrue(np.all(values < 65_521))
        self.assertTrue(all(len(set(values[:, index])) == 10 for index in range(100)))

    def test_gradient_quantization_is_distinct_and_nearly_preserves_median(self):
        rng = np.random.default_rng(11)
        gradients = rng.normal(0, 0.02, size=(10, 500))
        codes, bound, buckets = quantize_distinct(gradients, L=32)
        self.assertTrue(all(len(set(codes[:, index])) == 10 for index in range(500)))
        decoded = dequantize(
            upper_median(codes), clients=10, bound=bound, buckets=buckets, L=32
        )
        np.testing.assert_allclose(decoded, upper_median(gradients), atol=1e-7)


class NetworkProfileTests(unittest.TestCase):
    def test_trace_model_adds_latency_and_serialization(self):
        estimated = estimate_runtime(
            2.0,
            100.0,
            20,
            latency_ms=50,
            bandwidth_mbps=100,
        )
        self.assertAlmostEqual(estimated, 11.0)


if __name__ == "__main__":
    unittest.main()
