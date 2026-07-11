import tempfile
import unittest
from pathlib import Path

from urp.cache import CacheEntry, URPCache
from urp.chunking import content_defined_chunks, fixed_chunks
from urp.classifier import classify
from urp.contracts import Contract, Manifest, WorkUnit, WorkUnitKind
from urp.entropy import byte_entropy
from urp.impact import ImpactModelError, model_impact
from urp.manifest_store import FileManifestStore, InMemoryManifestStore, SQLiteManifestStore
from urp.plan_store import FilePlanStore
from urp.platforms import built_in_platform_profiles, platform_matrix, platform_readiness
from urp.planner import plan_work_unit
from urp.schema_validation import SchemaValidationError, validate_named_schema, validate_schema
from urp.work_unit_store import FileWorkUnitStore, InMemoryWorkUnitStore
from urp import PolicyDecision, VerificationResult


class CoreTests(unittest.TestCase):
    def test_entropy_low_for_repeated_bytes(self):
        self.assertLess(byte_entropy(b"a" * 1024), 0.1)

    def test_entropy_higher_for_varied_bytes(self):
        self.assertGreater(byte_entropy(bytes(range(256)) * 4), 7.5)

    def test_classifier_detects_prompt_task(self):
        wu = WorkUnit(kind=WorkUnitKind.PROMPT_REQUEST, tenant="t", logical_ref="app://q", payload="summarize this")
        self.assertEqual(classify(wu).ai_task_hint, "summarization")

    def test_chunkers_reassemble(self):
        data = (b"abc123" * 2000) + b"tail"
        chunks = content_defined_chunks(data, min_size=64, avg_bits=6, max_size=256)
        self.assertEqual(b"".join(c.data for c in chunks), data)
        self.assertGreater(len(chunks), 1)
        self.assertEqual([c.data for c in fixed_chunks(b"0123456789", 3)], [b"012", b"345", b"678", b"9"])

    def test_planner_for_data_includes_manifest_and_verify(self):
        wu = WorkUnit(kind=WorkUnitKind.BYTE_OBJECT, tenant="t", logical_ref="s3://b/k", payload="hello hello hello")
        plan = plan_work_unit(wu)
        self.assertIn("manifest", [a.type for a in plan.actions])
        self.assertIn("verify_restore", [a.type for a in plan.actions])
        self.assertIn("semantic_summary", plan.expected["denied_actions"])
        self.assert_plan_score_is_explainable(plan.expected)

    def test_planner_for_prompt_includes_model_route(self):
        wu = WorkUnit(kind=WorkUnitKind.PROMPT_REQUEST, tenant="t", logical_ref="app://chat", payload="classify this")
        plan = plan_work_unit(wu)
        self.assertIn("model_route", [a.type for a in plan.actions])
        self.assertEqual(plan.fallback, "call_baseline_model_provider")
        self.assertIn("semantic_cache_lookup", plan.expected["denied_actions"])
        self.assert_plan_score_is_explainable(plan.expected)

    def test_planner_for_embedding_includes_cache_route_and_compute_manifest(self):
        wu = WorkUnit(kind=WorkUnitKind.EMBEDDING_REQUEST, tenant="t", logical_ref="app://embed", payload={"input_hash": "abc"})
        plan = plan_work_unit(wu)
        actions = [a.type for a in plan.actions]
        self.assertIn("exact_cache_lookup", actions)
        self.assertIn("model_route", actions)
        self.assertIn("compute_manifest", actions)
        self.assertEqual(plan.fallback, "call_baseline_embedding_provider")
        self.assertIn("embedding_shape", plan.expected["required_verifiers"])
        self.assert_plan_score_is_explainable(plan.expected)

    def test_planner_scores_encrypted_data_lower_than_compressible_data(self):
        compressible = plan_work_unit(WorkUnit(kind=WorkUnitKind.BYTE_OBJECT, tenant="t", logical_ref="s3://b/plain", payload=b"a" * 4096))
        encrypted = plan_work_unit(WorkUnit(kind=WorkUnitKind.BYTE_OBJECT, tenant="t", logical_ref="s3://b/cipher", payload=bytes(range(256)) * 16))
        self.assertGreater(compressible.expected["score"], encrypted.expected["score"])
        self.assertGreater(compressible.expected["score_components"]["savings_value"], encrypted.expected["score_components"]["savings_value"])

    def test_cache_does_not_cross_tenants_and_requires_verifier(self):
        cache = URPCache()
        key = cache.exact_key("a", "ns", {"q": "hello"}, {"doc1"})
        cache.put(CacheEntry(key=key, tenant="a", namespace="ns", value="answer", source_fingerprints={"doc1"}, verifier_passed=True))
        self.assertEqual(cache.get(key, "a", "ns", {"doc1"}), "answer")
        self.assertIsNone(cache.get(key, "b", "ns", {"doc1"}))
        self.assertIsNone(cache.get(key, "a", "ns", {"doc2"}))
        with self.assertRaises(ValueError):
            cache.put(CacheEntry(key="bad", tenant="a", namespace="ns", value="bad", verifier_passed=False))

    def test_manifest_stores_roundtrip(self):
        wu = WorkUnit(kind=WorkUnitKind.BYTE_OBJECT, tenant="t", logical_ref="s3://b/k")
        mf = Manifest(work_unit_id=wu.id, tenant=wu.tenant, kind=wu.kind, contract=Contract.EXACT_BYTES, logical_ref=wu.logical_ref)
        mem = InMemoryManifestStore()
        mem.put(mf)
        self.assertEqual(mem.get_by_work_unit(wu.id).manifest_id, mf.manifest_id)
        with tempfile.TemporaryDirectory() as td:
            file_store = FileManifestStore(Path(td) / "manifests")
            file_store.put(mf)
            self.assertEqual(file_store.get(mf.manifest_id).work_unit_id, wu.id)
            sqlite_store = SQLiteManifestStore(Path(td) / "manifests.sqlite3")
            sqlite_store.put(mf)
            self.assertEqual(sqlite_store.get_by_work_unit(wu.id).manifest_id, mf.manifest_id)

    def test_manifest_stores_reject_invalid_compute_manifest(self):
        wu = WorkUnit(kind=WorkUnitKind.PROMPT_REQUEST, tenant="t", logical_ref="app://chat")
        mf = Manifest(
            work_unit_id=wu.id,
            tenant=wu.tenant,
            kind=wu.kind,
            contract=Contract.SEMANTIC,
            logical_ref=wu.logical_ref,
            physical={
                "compute_manifest": {
                    "request": {"request_hash": "abc", "tenant": "t", "task_type": "prompt_request"},
                    "contract": {"quality_required": "standard", "privacy_scope": "tenant_namespace"},
                    "plan": {"cache_checked": True, "selected_model": "tiny"},
                    "result": {
                        "accepted_by_verifier": True,
                        "cacheable_until": "local-session",
                        "estimated_joules_avoided": 0.0,
                    },
                }
            },
        )
        with self.assertRaises(SchemaValidationError):
            InMemoryManifestStore().put(mf)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SchemaValidationError):
                FileManifestStore(Path(td) / "manifests").put(mf)
            with self.assertRaises(SchemaValidationError):
                SQLiteManifestStore(Path(td) / "manifests.sqlite3").put(mf)

    def test_work_unit_stores_roundtrip(self):
        wu = WorkUnit(kind=WorkUnitKind.BYTE_OBJECT, tenant="t", logical_ref="s3://b/k", payload=b"bytes")
        mem = InMemoryWorkUnitStore()
        mem.put(wu)
        self.assertEqual(mem.get(wu.id).logical_ref, wu.logical_ref)
        with tempfile.TemporaryDirectory() as td:
            store = FileWorkUnitStore(Path(td) / "work_units")
            store.put(wu)
            restored = store.get(wu.id)
            self.assertEqual(restored.payload, b"bytes")
            self.assertEqual(store.list("t")[0].id, wu.id)

    def test_work_unit_stores_reject_empty_required_strings(self):
        invalid_tenant = WorkUnit(kind=WorkUnitKind.BYTE_OBJECT, tenant="", logical_ref="s3://b/k")
        invalid_ref = WorkUnit(kind=WorkUnitKind.BYTE_OBJECT, tenant="t", logical_ref="")
        with self.assertRaises(SchemaValidationError):
            InMemoryWorkUnitStore().put(invalid_tenant)
        with self.assertRaises(SchemaValidationError):
            InMemoryWorkUnitStore().put(invalid_ref)
        with tempfile.TemporaryDirectory() as td:
            store = FileWorkUnitStore(Path(td) / "work_units")
            with self.assertRaises(SchemaValidationError):
                store.put(invalid_tenant)
            with self.assertRaises(SchemaValidationError):
                store.put(invalid_ref)

    def test_plan_store_roundtrip(self):
        wu = WorkUnit(kind=WorkUnitKind.BYTE_OBJECT, tenant="t", logical_ref="s3://b/k", payload="hello")
        plan = plan_work_unit(wu)
        with tempfile.TemporaryDirectory() as td:
            store = FilePlanStore(Path(td) / "plans")
            store.put(plan)
            restored = store.get(plan.plan_id)
            self.assertEqual(restored.plan_id, plan.plan_id)
            self.assertEqual(restored.work_unit_id, wu.id)
            self.assertEqual(store.list(wu.id)[0].plan_id, plan.plan_id)

    def test_schema_validation(self):
        wu = WorkUnit(kind=WorkUnitKind.BYTE_OBJECT, tenant="t", logical_ref="s3://b/k", payload="hello")
        validate_named_schema("work_unit", wu.to_dict())
        self.assertTrue(wu.trace_id.startswith("tr_"))
        mf = Manifest(work_unit_id=wu.id, tenant=wu.tenant, kind=wu.kind, contract=Contract.EXACT_BYTES, logical_ref=wu.logical_ref)
        validate_named_schema("manifest", mf.to_dict())
        self.assertTrue(plan_work_unit(wu).to_dict()["trace_id"].startswith("tr_"))

    def test_schema_validation_enforces_length_item_and_numeric_bounds(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 2, "maxLength": 4},
                "items": {"type": "array", "minItems": 1, "maxItems": 2},
                "ratio": {"type": "number", "minimum": 0, "maximum": 1},
            },
        }
        validate_schema({"name": "abc", "items": [1], "ratio": 0.5}, schema)
        for payload in [
            {"name": "a", "items": [1], "ratio": 0.5},
            {"name": "abcde", "items": [1], "ratio": 0.5},
            {"name": "abc", "items": [], "ratio": 0.5},
            {"name": "abc", "items": [1, 2, 3], "ratio": 0.5},
            {"name": "abc", "items": [1], "ratio": 2},
        ]:
            with self.assertRaises(SchemaValidationError):
                validate_schema(payload, schema)

    def test_compute_manifest_schema_validation_and_public_verification_result(self):
        validate_named_schema(
            "compute_manifest",
            {
                "request": {
                    "request_hash": "abc",
                    "tenant": "t",
                    "task_type": "prompt_request",
                    "input_tokens": 3,
                },
                "contract": {
                    "quality_required": "standard",
                    "privacy_scope": "tenant_namespace",
                },
                "plan": {
                    "cache_checked": True,
                    "selected_model": "tiny",
                },
                "result": {
                    "accepted_by_verifier": True,
                    "fallback_used": False,
                    "cacheable_until": "local-session",
                    "estimated_joules_avoided": 0.0,
                },
            },
        )
        with self.assertRaises(SchemaValidationError):
            validate_named_schema(
                "compute_manifest",
                {
                    "request": {"request_hash": "abc", "tenant": "t", "task_type": "prompt_request"},
                    "contract": {"quality_required": "standard", "privacy_scope": "tenant_namespace"},
                    "plan": {"cache_checked": True, "selected_model": "tiny"},
                    "result": {
                        "accepted_by_verifier": True,
                        "fallback_used": False,
                        "cacheable_until": "local-session",
                        "estimated_joules_avoided": 0.0,
                    },
                },
            )
        self.assertTrue(VerificationResult(True, "test@0", "ok").to_dict()["accepted"])
        self.assertEqual(
            PolicyDecision(Contract.EXACT_BYTES, ["hash"], ["delete"]).to_dict()["contract"],
            "exact_bytes",
        )

    def test_all_platform_profiles_are_contract_ready_without_live_credentials(self):
        root = Path(__file__).resolve().parents[2]
        profiles = built_in_platform_profiles()
        for target in ["local", "kubernetes", "aws", "azure", "gcp", "on_prem", "edge", "openai_compatible", "cicd"]:
            self.assertIn(target, profiles)
        matrix = platform_matrix(root, env={})
        self.assertEqual(matrix["platform_count"], len(profiles))
        self.assertEqual(matrix["contract_ready_count"], matrix["platform_count"])
        self.assertLess(matrix["live_ready_count"], matrix["platform_count"])
        aws_live = platform_readiness("aws", root, env={}, require_live=True)
        self.assertTrue(aws_live.contract_ready)
        self.assertFalse(aws_live.live_ready)
        self.assertFalse(aws_live.passed)
        self.assertIn("AWS_REGION", aws_live.details["missing_live_env"])
        local = platform_readiness("local", root, env={})
        self.assertTrue(local.contract_ready)
        self.assertTrue(local.live_ready)

    def test_impact_model_keeps_assumptions_and_net_costs_explicit(self):
        result = model_impact(
            {
                "name": "test",
                "currency": "USD",
                "storage_gib": 102400,
                "storage_reduction_rate": 0.30,
                "storage_cost_per_gib_month": 0.023,
                "monthly_data_transfer_gib": 204800,
                "data_transfer_reduction_rate": 0.30,
                "data_transfer_cost_per_gib": 0.05,
                "monthly_ai_requests": 10000000,
                "average_input_tokens": 1000,
                "average_output_tokens": 250,
                "exact_cache_hit_rate": 0.15,
                "context_compiler_coverage": 0.40,
                "context_input_reduction_rate": 0.30,
                "ai_input_cost_per_million_tokens": 1.0,
                "ai_output_cost_per_million_tokens": 4.0,
                "monthly_urp_operating_cost": 2500,
                "implementation_cost": 30000,
                "analysis_horizon_months": 36,
            }
        )
        self.assertEqual(result["classification"], "modeled_scenario_not_forecast")
        self.assertEqual(result["monthly_avoided_work"]["model_calls"], 1_500_000)
        self.assertEqual(result["monthly_avoided_work"]["input_tokens"], 2_520_000_000)
        self.assertEqual(result["monthly_avoided_work"]["output_tokens"], 375_000_000)
        self.assertEqual(result["financial_impact"]["gross_monthly_savings"], 7798.56)
        self.assertEqual(result["financial_impact"]["net_monthly_savings"], 5298.56)
        self.assertEqual(result["financial_impact"]["payback_months"], 5.66)
        self.assertFalse(result["environmental_impact"]["estimated"])

    def test_impact_model_rejects_rates_outside_unit_interval(self):
        with self.assertRaises(ImpactModelError):
            model_impact(
                {
                    "name": "bad",
                    "currency": "USD",
                    "storage_gib": 1,
                    "storage_reduction_rate": 1.1,
                    "storage_cost_per_gib_month": 1,
                    "monthly_data_transfer_gib": 1,
                    "data_transfer_reduction_rate": 0,
                    "data_transfer_cost_per_gib": 1,
                    "monthly_ai_requests": 1,
                    "average_input_tokens": 1,
                    "average_output_tokens": 1,
                    "exact_cache_hit_rate": 0,
                    "context_compiler_coverage": 0,
                    "context_input_reduction_rate": 0,
                    "ai_input_cost_per_million_tokens": 1,
                    "ai_output_cost_per_million_tokens": 1,
                    "monthly_urp_operating_cost": 0,
                    "implementation_cost": 0,
                    "analysis_horizon_months": 1,
                }
            )

    def assert_plan_score_is_explainable(self, expected):
        components = expected["score_components"]
        for key in [
            "savings_value",
            "latency_penalty",
            "risk_penalty",
            "cpu_overhead",
            "rehydration_penalty",
            "metadata_overhead",
            "verifier_cost",
            "policy_bonus",
        ]:
            self.assertIn(key, components)
        self.assertIn("savings_value - latency_penalty", expected["score_formula"])
        self.assertGreaterEqual(expected["score"], 0.0)
        self.assertLessEqual(expected["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
