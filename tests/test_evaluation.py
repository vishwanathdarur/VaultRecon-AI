"""
Unit tests for evaluation metrics and benchmark runner.
"""

import shutil
import unittest
from evaluation.benchmark import BenchmarkRunner
from ai.llm import MockLLMProvider


class TestEvaluation(unittest.TestCase):
    def test_benchmark_runner_50_records(self):
        test_dir = "./testdb_eval_unit"
        shutil.rmtree(test_dir, ignore_errors=True)

        runner = BenchmarkRunner(db_dir=test_dir, llm_provider=MockLLMProvider())
        metrics = runner.run_benchmark(record_count=50)

        self.assertEqual(metrics.total_records, 50)
        self.assertGreater(metrics.deterministic_matched, 0)
        self.assertGreater(metrics.exceptions_generated, 0)
        self.assertGreater(metrics.ai_resolved, 0)
        self.assertGreaterEqual(metrics.ground_truth_accuracy, 0.90)
        self.assertGreater(metrics.ingestion_throughput, 1000.0)
        self.assertGreater(metrics.recon_throughput, 1000.0)
        self.assertGreater(metrics.p50_latency_ms, 0.0)

        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

