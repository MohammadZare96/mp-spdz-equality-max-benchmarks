import csv
import random
import tempfile
import unittest
from pathlib import Path

from benchmarks.plot_results import plot_one
from benchmarks.run_benchmarks import (
    GLOBAL_COMM_RE,
    PARTY_COMM_RE,
    RESULT_RE,
    TIME_RE,
    encode,
    partition_vector,
    requested_cases,
    zero_coded_vector,
)


class EncodingTests(unittest.TestCase):
    def test_partition_vector_matches_paper_example(self):
        self.assertEqual(partition_vector(10, 4), [1, 2, 5, 10])

    def test_zero_code_has_required_entries_for_zero_bits(self):
        rng = random.Random(7)
        encoded = zero_coded_vector(9, 4, 13, rng)
        self.assertEqual(encoded[1], 3)  # prefix "1" followed by "1"
        self.assertEqual(encoded[2], 5)  # prefix "10" followed by "1"

    def test_comparison_zero_criterion(self):
        prime = 251
        rng = random.Random(11)
        for left in range(128, prime):
            for right in range(128, prime):
                left_partition = encode(left, 8, prime, rng)[:8]
                right_zero = encode(right, 8, prime, rng)[8:]
                product = 1
                for a, b in zip(left_partition, right_zero):
                    product = product * (a - b) % prime
                self.assertEqual(product == 0, left > right)

    def test_requested_matrix_has_four_families_and_24_cases(self):
        cases = requested_cases()
        self.assertEqual(len(cases), 24)
        self.assertEqual(
            {(case.sweep, case.operation) for case in cases},
            {
                ("vary_L", "equality"),
                ("vary_L", "max"),
                ("vary_KN", "equality"),
                ("vary_KN", "max"),
            },
        )


class OutputParsingTests(unittest.TestCase):
    SAMPLE = """Time = 0.0123 seconds
Data sent = 1.25 MB in ~7 rounds (party 0 only)
Global data sent = 10.0 MB (all parties)
MAX_RESULT 42
"""

    def test_metric_regexes(self):
        self.assertEqual(TIME_RE.findall(self.SAMPLE), ["0.0123"])
        self.assertEqual(GLOBAL_COMM_RE.findall(self.SAMPLE), ["10.0"])
        self.assertEqual(PARTY_COMM_RE.findall(self.SAMPLE), [("1.25", "7")])
        self.assertEqual(RESULT_RE["max"].findall(self.SAMPLE), ["42"])


class PlotTests(unittest.TestCase):
    def test_plot_is_written_as_pdf_and_png(self):
        rows = []
        for operation, multiplier in (("equality", 1.0), ("max", 3.0)):
            for length in (8, 16, 32, 64):
                rows.append(
                    {
                        "sweep": "vary_L",
                        "operation": operation,
                        "L": str(length),
                        "K": "8",
                        "N": "8",
                        "runtime_median_seconds": str(length * multiplier / 1000),
                        "runtime_p25_seconds": str(length * multiplier / 1100),
                        "runtime_p75_seconds": str(length * multiplier / 900),
                    }
                )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runtime"
            plot_one(
                rows,
                "vary_L",
                "runtime",
                "Test runtime",
                "Runtime (seconds)",
                output,
                False,
            )
            self.assertGreater(output.with_suffix(".pdf").stat().st_size, 0)
            self.assertGreater(output.with_suffix(".png").stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
