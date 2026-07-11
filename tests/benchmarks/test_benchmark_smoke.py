import tempfile
import unittest

from urp.benchmarks import run_benchmark_suite


class BenchmarkSmokeTests(unittest.TestCase):
    def test_object_exact_suite(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_benchmark_suite("object-exact-v1", td)
            self.assertTrue(result["accepted"])
            self.assertEqual(result["bytes_in"], result["bytes_restored"])

    def test_prompt_cache_suite(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_benchmark_suite("prompt-cache-v1", td)
            self.assertTrue(result["accepted"])
            self.assertEqual(result["second_cache"], "exact_hit")
            self.assertEqual(result["model_calls_avoided"], 1)

    def test_local_all_suite(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_benchmark_suite("local-all-v1", td)
            self.assertEqual(result["suite"], "local-all-v1")
            self.assertEqual(len(result["results"]), 4)
            self.assertTrue(all(row["accepted"] for row in result["results"]))

    def test_advanced_local_suite(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_benchmark_suite("advanced-local-v1", td)
            self.assertTrue(result["accepted"])
            self.assertEqual(result["lakehouse_groups"], 1)
            self.assertEqual(result["training_duplicates"], 1)
            self.assertGreater(result["scheduler_shifted_seconds"], 0)

    def test_load_local_suite(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_benchmark_suite("load-local-v1", td)
            self.assertTrue(result["accepted"])
            self.assertGreater(result["object_ingest"]["objects_per_second"], 0)
            self.assertGreater(result["rehydration_latency"]["p95_seconds"], 0)
            self.assertGreater(result["ai_gateway_latency"]["p95_seconds"], 0)
            self.assertEqual(result["cache_index_scalability"]["entries"], result["cache_index_scalability"]["hits"])
            self.assertGreater(result["manifest_store_write_rate"]["manifests_per_second"], 0)


if __name__ == "__main__":
    unittest.main()
