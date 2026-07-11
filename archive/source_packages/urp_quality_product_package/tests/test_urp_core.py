import unittest
from urp.contracts import WorkUnit, WorkUnitKind, Contract, Manifest
from urp.entropy import byte_entropy
from urp.classifier import classify
from urp.chunking import content_defined_chunks
from urp.planner import plan_work_unit
from urp.cache import URPCache, CacheEntry
from urp.manifest_store import InMemoryManifestStore


class URPCoreTests(unittest.TestCase):
    def test_entropy_low_for_repeated_bytes(self):
        self.assertLess(byte_entropy(b"a" * 1024), 0.1)

    def test_entropy_higher_for_varied_bytes(self):
        data = bytes(range(256)) * 4
        self.assertGreater(byte_entropy(data), 7.5)

    def test_classifier_detects_prompt_task(self):
        wu = WorkUnit(kind=WorkUnitKind.PROMPT_REQUEST, tenant="t", logical_ref="app://q", payload="summarize this")
        c = classify(wu)
        self.assertEqual(c.ai_task_hint, "summarization")

    def test_chunker_reassembles(self):
        data = (b"abc123" * 2000) + b"tail"
        chunks = content_defined_chunks(data, min_size=64, avg_bits=6, max_size=256)
        self.assertEqual(b"".join(c.data for c in chunks), data)
        self.assertGreater(len(chunks), 1)

    def test_planner_for_data_includes_manifest_and_verify(self):
        wu = WorkUnit(kind=WorkUnitKind.BYTE_OBJECT, tenant="t", logical_ref="s3://b/k", payload="hello hello hello")
        plan = plan_work_unit(wu)
        action_types = [a.type for a in plan.actions]
        self.assertIn("manifest", action_types)
        self.assertIn("verify_restore", action_types)

    def test_planner_for_prompt_includes_model_route(self):
        wu = WorkUnit(kind=WorkUnitKind.PROMPT_REQUEST, tenant="t", logical_ref="app://chat", payload="classify this")
        plan = plan_work_unit(wu)
        self.assertIn("model_route", [a.type for a in plan.actions])
        self.assertEqual(plan.fallback, "call_baseline_model_provider")

    def test_cache_does_not_cross_tenants(self):
        cache = URPCache()
        key = cache.exact_key("a", "ns", {"q": "hello"}, {"doc1"})
        cache.put(CacheEntry(key=key, tenant="a", namespace="ns", value="answer", source_fingerprints={"doc1"}, verifier_passed=True))
        self.assertEqual(cache.get(key, "a", "ns", {"doc1"}), "answer")
        self.assertIsNone(cache.get(key, "b", "ns", {"doc1"}))

    def test_cache_requires_verifier(self):
        cache = URPCache()
        with self.assertRaises(ValueError):
            cache.put(CacheEntry(key="k", tenant="a", namespace="n", value="bad", verifier_passed=False))

    def test_manifest_store_roundtrip(self):
        store = InMemoryManifestStore()
        wu = WorkUnit(kind=WorkUnitKind.BYTE_OBJECT, tenant="t", logical_ref="s3://b/k")
        mf = Manifest(work_unit_id=wu.id, tenant=wu.tenant, kind=wu.kind, contract=Contract.EXACT_BYTES, logical_ref=wu.logical_ref)
        store.put(mf)
        self.assertEqual(store.get_by_work_unit(wu.id).manifest_id, mf.manifest_id)


if __name__ == "__main__":
    unittest.main()
