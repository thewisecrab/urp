import tempfile
import unittest

from urp.benchmarks import run_benchmark_suite


class LocalLoadTests(unittest.TestCase):
    def test_load_suite_reports_documented_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_benchmark_suite("load-local-v1", td)
            self.assertTrue(result["accepted"])
            for key in [
                "object_ingest",
                "rehydration_latency",
                "ai_gateway_latency",
                "cache_index_scalability",
                "manifest_store_write_rate",
            ]:
                self.assertIn(key, result)
            self.assertGreater(result["object_ingest"]["bytes_per_second"], 0)
            self.assertGreaterEqual(result["rehydration_latency"]["operations"], 1)
            self.assertGreaterEqual(result["ai_gateway_latency"]["operations"], 1)
            self.assertEqual(result["cache_index_scalability"]["entries"], result["cache_index_scalability"]["hits"])
            self.assertGreater(result["manifest_store_write_rate"]["manifests_per_second"], 0)


if __name__ == "__main__":
    unittest.main()
