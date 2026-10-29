import tempfile
import unittest
from dataclasses import FrozenInstanceError

from urp.ai_gateway import handle_chat_completion
from urp.ai_router import KeywordModelRouter, ModelRoute
from urp.context import ContextChunk, compile_context, compile_openai_messages
from urp.contracts import WorkUnit, WorkUnitKind
from urp.errors import verifier_failed
from urp.decision_backend import KeywordDecisionBackend
from urp.impact import ImpactModelError, model_impact, rebound_indicator
from urp.ledger import default_ledger
from urp.provider_usage import extract_provider_cache_usage
from urp.semantic_cache import LexicalJaccardScorer, SemanticCache, SemanticCacheEntry
from urp.tracing import default_trace_store
from urp.verifiers import VerificationResult


def _base_scenario(**overrides):
    payload = {
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
    payload.update(overrides)
    return payload


class FrozenErrorCompatibilityTest(unittest.TestCase):
    def test_handled_exception_can_clear_traceback_without_unfreezing_fields(self):
        error = verifier_failed("cache value verification failed")
        error.__traceback__ = None
        self.assertIsNone(error.__traceback__)
        with self.assertRaises(FrozenInstanceError):
            error.message = "changed"


class ImpactAccountingTest(unittest.TestCase):
    def test_list_price_keeps_historical_totals_and_flags_them(self):
        result = model_impact(_base_scenario())
        self.assertEqual(result["financial_impact"]["gross_monthly_savings"], 7798.56)
        self.assertEqual(result["financial_impact"]["net_monthly_savings"], 5298.56)
        self.assertEqual(result["financial_impact"]["gross_ai_cost_avoided"], result["financial_impact"]["monthly_ai_cost_avoided"])
        self.assertEqual(result["financial_impact"]["gross_storage_cost_avoided"], 706.56)
        self.assertFalse(result["rebound_adjusted"])
        self.assertFalse(result["financial_impact"]["rebound_adjusted"])
        self.assertEqual(result["attribution"], "gross_attributional_constant_demand")
        self.assertEqual(result["input_pricing"]["mode"], "list_price")
        self.assertTrue(result["input_pricing"]["backward_compatible_list_price"])
        self.assertFalse(result["input_pricing"]["cache_discount_applied"])
        self.assertIn("overstate", result["input_pricing"]["note"])

    def test_effective_blended_rate_discounts_avoided_input(self):
        scenario = {
            "name": "cache",
            "currency": "USD",
            "storage_gib": 0,
            "storage_reduction_rate": 0,
            "storage_cost_per_gib_month": 0,
            "monthly_data_transfer_gib": 0,
            "data_transfer_reduction_rate": 0,
            "data_transfer_cost_per_gib": 0,
            "monthly_ai_requests": 1000,
            "average_input_tokens": 1000,
            "average_output_tokens": 0,
            "exact_cache_hit_rate": 1,
            "context_compiler_coverage": 0,
            "context_input_reduction_rate": 0,
            "ai_input_cost_per_million_tokens": 1.0,
            "ai_output_cost_per_million_tokens": 4.0,
            "monthly_urp_operating_cost": 0,
            "implementation_cost": 0,
            "analysis_horizon_months": 1,
            "input_pricing": "effective_blended",
            "provider_cache_read_share": 1,
            "cache_read_price_ratio": 0.1,
        }
        listed = model_impact({**scenario, "input_pricing": "list_price", "provider_cache_read_share": None, "cache_read_price_ratio": None})
        blended = model_impact(scenario)
        self.assertEqual(listed["financial_impact"]["gross_ai_cost_avoided"], 1.0)
        self.assertEqual(blended["financial_impact"]["gross_ai_cost_avoided"], 0.1)
        self.assertEqual(blended["input_pricing"]["effective_input_price_ratio"], 0.1)
        self.assertFalse(blended["input_pricing"]["cache_write_premium_applied"])
        self.assertFalse(blended["rebound_adjusted"])

    def test_write_premium_and_read_ratio_blend(self):
        result = model_impact(
            {
                "name": "blend",
                "currency": "USD",
                "storage_gib": 0,
                "storage_reduction_rate": 0,
                "storage_cost_per_gib_month": 0,
                "monthly_data_transfer_gib": 0,
                "data_transfer_reduction_rate": 0,
                "data_transfer_cost_per_gib": 0,
                "monthly_ai_requests": 1,
                "average_input_tokens": 1_000_000,
                "average_output_tokens": 0,
                "exact_cache_hit_rate": 1,
                "context_compiler_coverage": 0,
                "context_input_reduction_rate": 0,
                "ai_input_cost_per_million_tokens": 1.0,
                "ai_output_cost_per_million_tokens": 1.0,
                "monthly_urp_operating_cost": 0,
                "implementation_cost": 0,
                "analysis_horizon_months": 1,
                "input_pricing": "effective_blended",
                "provider_cache_read_share": 0.5,
                "provider_cache_write_share": 0.25,
                "cache_read_price_ratio": 0.1,
                "cache_write_premium": 2,
            }
        )
        self.assertEqual(result["input_pricing"]["effective_input_price_ratio"], 0.8)
        self.assertEqual(result["financial_impact"]["gross_ai_cost_avoided"], 0.8)
        self.assertTrue(result["input_pricing"]["cache_write_premium_applied"])

    def test_cache_fields_are_rejected_on_the_list_price_path(self):
        with self.assertRaises(ImpactModelError):
            model_impact(_base_scenario(provider_cache_read_share=0.5, cache_read_price_ratio=0.1))

    def test_effective_mode_requires_an_explicit_read_ratio(self):
        with self.assertRaises(ImpactModelError):
            model_impact(_base_scenario(input_pricing="effective_blended", provider_cache_read_share=0.2))

    def test_fixed_plus_per_token_energy_is_gross_and_operator_supplied(self):
        result = model_impact(
            _base_scenario(
                energy_kwh_fixed_per_avoided_call=0.001,
                energy_kwh_per_token=0.000001,
                grid_kg_co2e_per_kwh=0.4,
            )
        )
        energy = result["environmental_impact"]
        self.assertEqual(energy["model"], "fixed_plus_per_token")
        self.assertFalse(energy["rebound_adjusted"])
        self.assertEqual(energy["monthly_kwh_avoided"], energy["gross_monthly_kwh_avoided"])
        self.assertGreater(energy["gross_monthly_kwh_avoided"], 0)
        self.assertIn("gross_monthly_kg_co2e_avoided", energy)
        self.assertEqual(energy["monthly_kg_co2e_avoided"], energy["gross_monthly_kg_co2e_avoided"])
        calls = 1_500_000
        avoided_call_tokens = 1_500_000_000 + 375_000_000
        context_tokens = 1_020_000_000
        expected = calls * 0.001 + (avoided_call_tokens + context_tokens) * 0.000001
        self.assertEqual(energy["gross_monthly_kwh_avoided"], round(expected, 6))

    def test_per_call_energy_does_not_include_context_tokens(self):
        per_call = model_impact(_base_scenario(energy_kwh_per_avoided_model_call=0.002))
        self.assertEqual(per_call["environmental_impact"]["model"], "per_call")
        self.assertEqual(per_call["environmental_impact"]["gross_monthly_kwh_avoided"], 3000)
        with self.assertRaises(ImpactModelError):
            model_impact(
                _base_scenario(
                    energy_kwh_per_avoided_model_call=0.002,
                    energy_kwh_fixed_per_avoided_call=0.001,
                    energy_kwh_per_token=0.000001,
                )
            )
        with self.assertRaises(ImpactModelError):
            model_impact(_base_scenario(energy_kwh_fixed_per_avoided_call=0.001))

    def test_rebound_indicator_is_labelled_and_not_a_measurement(self):
        matched = rebound_indicator(actual_absolute_reduction=10, expected_gross_reduction=10)
        self.assertEqual(matched["R"], 0)
        self.assertFalse(matched["measured"])
        self.assertEqual(rebound_indicator(0, 10)["R"], 1)
        self.assertEqual(rebound_indicator(-5, 10)["R"], 1.5)
        with self.assertRaises(ImpactModelError):
            rebound_indicator(1, 0)


class ProviderUsageTest(unittest.TestCase):
    def test_openai_cached_tokens_map_to_gen_ai_names(self):
        extracted = extract_provider_cache_usage(
            {
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                    "prompt_tokens_details": {"cached_tokens": 80},
                }
            }
        )
        self.assertTrue(extracted["cache_fields_present"])
        self.assertFalse(extracted["inferred"])
        self.assertEqual(extracted["gen_ai_usage"]["gen_ai.usage.input_tokens"], 100)
        self.assertEqual(extracted["gen_ai_usage"]["gen_ai.usage.output_tokens"], 20)
        self.assertEqual(extracted["gen_ai_usage"]["gen_ai.usage.cache_read.input_tokens"], 80)
        self.assertNotIn("gen_ai.usage.cache_creation.input_tokens", extracted["gen_ai_usage"])

    def test_anthropic_cache_tokens_are_added_into_the_input_total(self):
        extracted = extract_provider_cache_usage(
            {
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 4,
                    "cache_read_input_tokens": 80,
                    "cache_creation_input_tokens": 5,
                }
            }
        )
        self.assertTrue(extracted["anthropic_cache_added_to_input_tokens"])
        self.assertEqual(extracted["gen_ai_usage"]["gen_ai.usage.input_tokens"], 95)
        self.assertEqual(extracted["gen_ai_usage"]["gen_ai.usage.cache_read.input_tokens"], 80)
        self.assertEqual(extracted["gen_ai_usage"]["gen_ai.usage.cache_creation.input_tokens"], 5)
        self.assertEqual(extracted["provider_usage"]["input_tokens"], 10)

    def test_missing_usage_is_not_invented(self):
        extracted = extract_provider_cache_usage({"id": "chatcmpl"})
        self.assertFalse(extracted["present"])
        self.assertFalse(extracted["cache_fields_present"])
        self.assertEqual(extracted["gen_ai_usage"], {})

    def test_conflicting_cache_read_fields_are_not_collapsed(self):
        extracted = extract_provider_cache_usage(
            {
                "usage": {
                    "prompt_tokens": 10,
                    "prompt_tokens_details": {"cached_tokens": 4},
                    "cache_read_input_tokens": 9,
                }
            }
        )
        self.assertIn("cache_read", extracted["conflicts"])
        self.assertIn("input_tokens", extracted["conflicts"])
        self.assertNotIn("gen_ai.usage.cache_read.input_tokens", extracted["gen_ai_usage"])
        self.assertEqual(extracted["provider_usage"]["prompt_tokens_details.cached_tokens"], 4)
        self.assertEqual(extracted["provider_usage"]["cache_read_input_tokens"], 9)


class _UsageProvider:
    def __init__(self, usage):
        self.usage = usage

    def chat(self, request, route):
        return {
            "id": "chatcmpl_usage",
            "object": "chat.completion",
            "model": route,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            "usage": self.usage,
        }


class GatewayCacheUsageTest(unittest.TestCase):
    def test_ledger_and_trace_record_provider_cache_fields(self):
        usage = {
            "prompt_tokens": 50,
            "completion_tokens": 5,
            "prompt_tokens_details": {"cached_tokens": 40},
        }
        with tempfile.TemporaryDirectory() as td:
            response = handle_chat_completion(
                {"model": "auto", "messages": [{"role": "user", "content": "hello cache"}]},
                tenant="tenant-usage",
                state_dir=td,
                provider=_UsageProvider(usage),
            )
            events = default_ledger(td).query(work_unit_id=response["urp"]["work_unit_id"])
            recorded = [event for event in events if event.event_type == "ai.provider_usage.recorded"]
            self.assertEqual(len(recorded), 1)
            self.assertEqual(recorded[0].details["gen_ai_usage"]["gen_ai.usage.cache_read.input_tokens"], 40)
            self.assertFalse(recorded[0].details["inferred"])
            spans = default_trace_store(td).query(trace_id=response["urp"]["trace_id"], name="urp.ai.usage")
            self.assertEqual(spans[0].attributes["gen_ai.usage.cache_read.input_tokens"], 40)

    def test_mock_usage_without_cache_fields_is_not_recorded_as_provider_cache(self):
        with tempfile.TemporaryDirectory() as td:
            response = handle_chat_completion(
                {"model": "auto", "messages": [{"role": "user", "content": "no provider cache field"}]},
                tenant="tenant-usage",
                state_dir=td,
            )
            events = default_ledger(td).query(work_unit_id=response["urp"]["work_unit_id"])
            self.assertFalse(any(event.event_type == "ai.provider_usage.recorded" for event in events))


class ContextCacheSafetyTest(unittest.TestCase):
    def test_historical_dedupe_still_drops_a_later_duplicate(self):
        chunks = [ContextChunk("repeat", "a"), ContextChunk("repeat", "a"), ContextChunk("long text", "b")]
        compiled = compile_context(chunks, max_tokens=10)
        self.assertEqual(len(compiled.chunks), 2)
        self.assertEqual(len(compiled.removed_fingerprints), 1)
        self.assertFalse(compiled.lossy_truncation_applied)

    def test_budget_drop_requires_explicit_opt_in(self):
        chunks = [ContextChunk("x" * 40, "a"), ContextChunk("y" * 40, "b")]
        kept = compile_context(chunks, max_tokens=5)
        self.assertEqual(len(kept.chunks), 2)
        self.assertTrue(kept.budget_truncation_skipped)
        self.assertFalse(kept.lossy_truncation_permitted)
        truncated = compile_context(chunks, max_tokens=10, allow_lossy_truncation=True)
        self.assertEqual([chunk.source_id for chunk in truncated.chunks], ["a"])
        self.assertTrue(truncated.lossy_truncation_applied)

    def test_cache_breakpoint_is_not_rewritten(self):
        chunks = [
            ContextChunk("x" * 40, "a", {"role": "system"}),
            ContextChunk("x" * 40, "b", {"role": "system", "cache_breakpoint": True}),
            ContextChunk("x" * 40, "c", {"role": "system"}),
            ContextChunk("z" * 80, "d", {"role": "system"}),
        ]
        compiled = compile_context(chunks, max_tokens=3, allow_lossy_truncation=True)
        self.assertEqual([chunk.source_id for chunk in compiled.chunks], ["a", "b"])
        self.assertTrue(compiled.cache_prefix_preserved)
        self.assertTrue(compiled.prefix_exceeds_budget)
        self.assertTrue(compiled.lossy_truncation_applied)

    def test_openai_breakpoint_on_a_user_message_freezes_the_prefix(self):
        messages = [
            {"role": "system", "content": "stable"},
            {"role": "user", "content": "question", "cache_control": {"type": "ephemeral"}},
            {"role": "system", "content": "stable"},
            {"role": "system", "content": "tail"},
        ]
        compiled, rendered = compile_openai_messages(messages, max_tokens=2, allow_lossy_truncation=True)
        self.assertEqual([message["content"] for message in rendered if message["role"] == "system"], ["stable"])
        self.assertEqual(rendered[1]["role"], "user")
        self.assertTrue(compiled.cache_prefix_preserved)
        self.assertNotIn("tail", [message["content"] for message in rendered])


class _FixedRouter:
    def route(self, work_unit, allowed_models=None, prompt_text=None):
        return ModelRoute("tiny", "pluggable_backend", "frontier", 0.1)


class _AlwaysMatch:
    def score(self, left, right):
        return 1.0


class PluggableDecisionTest(unittest.TestCase):
    def test_keyword_router_remains_the_default(self):
        work = WorkUnit(WorkUnitKind.PROMPT_REQUEST, "tenant", "ref")
        route = KeywordModelRouter().route(work, prompt_text="classify this label")
        self.assertEqual(route.model, "small")
        self.assertEqual(KeywordDecisionBackend().route(work, prompt_text="hello").model, "medium")

    def test_gateway_uses_an_injected_router(self):
        with tempfile.TemporaryDirectory() as td:
            response = handle_chat_completion(
                {"model": "auto", "messages": [{"role": "user", "content": "ordinary request"}]},
                tenant="tenant-router",
                state_dir=td,
                router=_FixedRouter(),
            )
            self.assertEqual(response["model"], "tiny")

    def test_semantic_cache_scorer_and_verifier_are_replaceable(self):
        accepted = VerificationResult(True, "custom@1", "ok")
        cache = SemanticCache(threshold=0.99, scorer=_AlwaysMatch(), verifier=lambda value: accepted)
        cache.put(
            SemanticCacheEntry(
                key="k",
                tenant="t",
                namespace="n",
                normalized_text="completely different words",
                value="stored",
                source_fingerprints={"src"},
                verification=accepted,
            )
        )
        hit = cache.lookup_hit("t", "n", "unrelated query text", {"src"})
        self.assertIsNotNone(hit)
        self.assertEqual(hit.value, "stored")
        self.assertEqual(hit.score, 1.0)
        self.assertLess(LexicalJaccardScorer().score("completely different words", "unrelated query text"), 0.82)


class ContextPolicyOptInTest(unittest.TestCase):
    def test_lossy_truncation_stays_off_unless_policy_and_request_allow_it(self):
        messages = [
            {"role": "system", "content": "P" * 20, "cache_control": {"type": "ephemeral"}},
            {"role": "system", "content": "Q" * 80},
            {"role": "user", "content": "question"},
        ]
        bundle = {
            "apiVersion": "urp.dev/v1",
            "kind": "ReductionPolicy",
            "metadata": {"name": "lossy-context", "version": "v1"},
            "spec": {
                "defaults": {"contract": "semantic", "modelAllowlist": ["tiny", "small", "medium", "frontier"]},
                "rules": [
                    {
                        "name": "truncate",
                        "match": {"kind": "prompt_request"},
                        "contract": "semantic",
                        "allow": {
                            "transforms": [
                                "normalize_prompt",
                                "context_compile",
                                "context_budget_truncate",
                                "model_route",
                                "verify",
                                "compute_manifest",
                            ]
                        },
                    }
                ],
            },
        }

        class CapturingProvider:
            def __init__(self):
                self.messages = []

            def chat(self, request, route):
                self.messages.append(request["messages"])
                return {
                    "id": "chatcmpl_ctx",
                    "object": "chat.completion",
                    "model": route,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "done"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
                }

        request = {"model": "auto", "messages": messages, "urp": {"max_context_tokens": 4, "allow_lossy_context_truncation": True}}
        with tempfile.TemporaryDirectory() as td:
            provider = CapturingProvider()
            handle_chat_completion(request, tenant="tenant-ctx", state_dir=td, provider=provider)
            self.assertEqual(len(provider.messages[0]), 3)
        with tempfile.TemporaryDirectory() as td:
            provider = CapturingProvider()
            opted = dict(request)
            opted["urp"] = {**request["urp"]}
            handle_chat_completion(opted, tenant="tenant-ctx", state_dir=td, provider=provider, policy_bundle=bundle)
            roles = [message["role"] for message in provider.messages[0]]
            self.assertEqual(roles, ["system", "user"])
            self.assertTrue(provider.messages[0][0]["content"].startswith("P"))


if __name__ == "__main__":
    unittest.main()
