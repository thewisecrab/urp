import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from urp.adapters import LocalS3Adapter, POSIXAdapter, built_in_adapters
from urp.ai_gateway import OpenAICompatibleProvider, handle_chat_completion, handle_completion, handle_embeddings
from urp.ai_router import RouteFeedbackStore
from urp.auth import APIKeyAuthenticator, Principal
from urp.cache import URPCache
from urp.checkpoints import CheckpointDeltaStore
from urp.context import ContextChunk, compile_context
from urp.contracts import WorkUnit, WorkUnitKind
from urp.disaster_recovery import export_state, import_state
from urp.executor import execute_work_unit, payload_to_bytes, rehydrate_manifest, rehydrate_manifest_range
from urp.errors import URPError
from urp.kms import LocalKMS
from urp.lakehouse import LakehouseFile, recommend_compaction
from urp.ledger import default_ledger
from urp.manifest_explorer import manifest_explorer_report
from urp.manifest_store import default_manifest_store
from urp.policy_store import PolicyBundleStore
from urp.production import production_readiness_check
from urp.reports import dashboard_report, savings_report
from urp.scheduler import FlexibleJob, SchedulerStore, schedule
from urp.schema_validation import validate_named_schema
from urp.service_runtime import create_service_server, service_health, service_specs
from urp.structured_logs import default_log_store, emit_log
from urp.training import TrainingSample, dedupe_training_samples
from urp.tracing import default_trace_store


_ADMIN_API_KEY = "test-admin-secret"
_VIEWER_API_KEY = "test-viewer-secret"
_GATEWAY_API_KEY = "test-gateway-secret"


def _test_authenticator() -> APIKeyAuthenticator:
    return APIKeyAuthenticator(
        {
            _ADMIN_API_KEY: Principal("integration-admin", "*", {"admin"}),
            _VIEWER_API_KEY: Principal("integration-viewer", "tenant-svc", {"viewer"}),
            _GATEWAY_API_KEY: Principal("integration-gateway", "tenant-svc", {"gateway"}),
        }
    )


def _plugin_descriptor(name: str) -> dict:
    return {
        "api_version": "urp.plugin.v1",
        "name": name,
        "version": "0.1.0",
        "category": "transforms",
        "capabilities": ["transform"],
        "contracts": ["exact_bytes"],
        "trust_level": "local",
        "entrypoint": "src/plugin.py",
        "entrypoint_sha256": "0" * 64,
        "network_access": False,
        "operations": ["transform"],
        "default_enabled": False,
    }


class RuntimeIntegrationTests(unittest.TestCase):
    def test_exact_object_execute_and_rehydrate(self):
        with tempfile.TemporaryDirectory() as td:
            data = (b"hello hello hello\n" * 2000) + b"tail"
            wu = WorkUnit(WorkUnitKind.BYTE_OBJECT, "tenant-a", "s3://b/k", data)
            result = execute_work_unit(wu, td)
            self.assertTrue(result.accepted)
            self.assertEqual(rehydrate_manifest(result.manifest_id, td), data)
            self.assertEqual(rehydrate_manifest_range(result.manifest_id, 2, 9, td), data[2:9])
            manifest = default_manifest_store(td).get(result.manifest_id)
            self.assertEqual(manifest.physical["whole_sha256"], result.output["sha256"])
            self.assertEqual(manifest.trace_id, wu.trace_id)
            self.assertTrue(default_ledger(td).verify_chain())
            self.assertTrue(default_ledger(td).read()[0].trace_id.startswith("tr_"))
            logs = default_log_store(td).query(tenant="tenant-a", work_unit_id=wu.id)
            log_types = {row.event_type for row in logs}
            self.assertIn("work_unit.received", log_types)
            self.assertIn("manifest.written", log_types)
            self.assertIn("logical_bytes", logs[0].details)
            self.assertNotIn("hello hello", json.dumps([row.to_dict() for row in logs]))
            span_names = {span.name for span in default_trace_store(td).query(trace_id=wu.trace_id)}
            self.assertIn("urp.intake", span_names)
            self.assertIn("urp.manifest.write", span_names)

    def test_structured_logs_redact_sensitive_fields_and_query(self):
        with tempfile.TemporaryDirectory() as td:
            entry = emit_log(
                td,
                "debug.prompt",
                "prompt: secret reset policy",
                tenant="tenant-log",
                work_unit_id="wu_log",
                trace_id="tr_log",
                details={"prompt": "secret reset policy", "nested": {"messages": ["secret reset policy"]}, "safe": "kept"},
            )
            rows = default_log_store(td).query(tenant="tenant-log", event_types=["debug.prompt"], trace_id="tr_log")
            self.assertEqual(entry.message, "[redacted]")
            self.assertEqual(rows[0].details["prompt"], "[redacted]")
            self.assertEqual(rows[0].details["nested"]["messages"], "[redacted]")
            self.assertEqual(rows[0].details["safe"], "kept")
            self.assertNotIn("secret reset policy", json.dumps(rows[0].to_dict()))

    def test_same_tenant_chunk_dedupe(self):
        with tempfile.TemporaryDirectory() as td:
            data = b"abc123" * 5000
            first = execute_work_unit(WorkUnit(WorkUnitKind.BYTE_OBJECT, "tenant-a", "s3://b/a", data), td)
            second = execute_work_unit(WorkUnit(WorkUnitKind.BYTE_OBJECT, "tenant-a", "s3://b/b", data), td)
            second_manifest = default_manifest_store(td).get(second.manifest_id)
            self.assertGreaterEqual(second_manifest.telemetry["dedupe_hits"], 1)
            self.assertNotEqual(first.manifest_id, second.manifest_id)

    def test_ai_gateway_exact_cache_hit(self):
        with tempfile.TemporaryDirectory() as td:
            request = {"model": "auto", "messages": [{"role": "user", "content": "Summarize reset policy"}]}
            first = handle_chat_completion(request, tenant="tenant-ai", namespace="support", state_dir=td)
            second = handle_chat_completion(request, tenant="tenant-ai", namespace="support", state_dir=td)
            self.assertEqual(first["urp"]["cache"], "miss")
            self.assertEqual(second["urp"]["cache"], "exact_hit")
            self.assertNotEqual(first["urp"]["manifest_id"], second["urp"]["manifest_id"])
            self.assertIn(first["urp"]["route"], RouteFeedbackStore(td).summary())
            first_manifest = default_manifest_store(td).get(first["urp"]["manifest_id"])
            second_manifest = default_manifest_store(td).get(second["urp"]["manifest_id"])
            validate_named_schema("compute_manifest", first_manifest.physical["compute_manifest"])
            validate_named_schema("compute_manifest", second_manifest.physical["compute_manifest"])
            self.assertFalse(second_manifest.physical["compute_manifest"]["result"]["large_model_called"])
            event_types = [event.event_type for event in default_ledger(td).query(work_unit_id=first["urp"]["work_unit_id"])]
            self.assertIn("policy.evaluated", event_types)
            self.assertIn("plan.created", event_types)

    def test_ai_gateway_verifier_failure_uses_fallback_and_records_manifest(self):
        class EmptyFirstProvider:
            def __init__(self):
                self.routes = []

            def chat(self, request, route):
                self.routes.append(route)
                content = "" if len(self.routes) == 1 else f"[fallback:{route}] recovered answer"
                return {
                    "id": "chatcmpl_fallback",
                    "object": "chat.completion",
                    "model": route,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1 if content else 0, "total_tokens": 2 if content else 1},
                }

        with tempfile.TemporaryDirectory() as td:
            cache = URPCache()
            provider = EmptyFirstProvider()
            request = {"model": "auto", "messages": [{"role": "user", "content": "Summarize fallback policy"}]}
            first = handle_chat_completion(request, tenant="tenant-fallback", namespace="support", state_dir=td, provider=provider, cache=cache)
            second = handle_chat_completion(request, tenant="tenant-fallback", namespace="support", state_dir=td, provider=provider, cache=cache)
            manifest = default_manifest_store(td).get(first["urp"]["manifest_id"])
            compute_manifest = manifest.physical["compute_manifest"]
            event_types = [event.event_type for event in default_ledger(td).query(work_unit_id=first["urp"]["work_unit_id"])]
            self.assertEqual(provider.routes, ["medium", "frontier"])
            self.assertTrue(first["urp"]["fallback_used"])
            self.assertEqual(first["urp"]["route"], "frontier")
            self.assertEqual(second["urp"]["cache"], "exact_hit")
            self.assertIn("ai.fallback.invoked", event_types)
            self.assertTrue(manifest.verification["accepted"])
            self.assertTrue(compute_manifest["result"]["fallback_used"])
            self.assertEqual(compute_manifest["result"]["fallback_reason"], "empty")
            self.assertTrue(compute_manifest["result"]["large_model_called"])
            validate_named_schema("compute_manifest", compute_manifest)

    def test_ai_gateway_rejects_cache_when_fallback_verifier_fails(self):
        class AlwaysEmptyProvider:
            def __init__(self):
                self.calls = 0

            def chat(self, request, route):
                self.calls += 1
                return {
                    "id": "chatcmpl_empty",
                    "object": "chat.completion",
                    "model": route,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1},
                }

        with tempfile.TemporaryDirectory() as td:
            cache = URPCache()
            provider = AlwaysEmptyProvider()
            request = {"model": "auto", "messages": [{"role": "user", "content": "Summarize failing fallback"}]}
            with self.assertRaises(URPError) as first_error:
                handle_chat_completion(request, tenant="tenant-fallback-fail", namespace="support", state_dir=td, provider=provider, cache=cache)
            with self.assertRaises(URPError) as second_error:
                handle_chat_completion(request, tenant="tenant-fallback-fail", namespace="support", state_dir=td, provider=provider, cache=cache)
            event_types = [event.event_type for event in default_ledger(td).query(tenant="tenant-fallback-fail")]
            self.assertEqual(first_error.exception.code, "verifier_failed")
            self.assertEqual(second_error.exception.code, "verifier_failed")
            self.assertEqual(provider.calls, 4)
            self.assertIn("ai.fallback.invoked", event_types)
            self.assertIn("verifier.failed", event_types)
            self.assertNotIn("cache.exact.hit", event_types)
            self.assertEqual(default_manifest_store(td).list("tenant-fallback-fail"), [])

    def test_ai_gateway_text_completion_exact_cache_hit(self):
        with tempfile.TemporaryDirectory() as td:
            request = {"model": "auto", "prompt": "Summarize legacy completion policy"}
            first = handle_completion(request, tenant="tenant-completion", namespace="legacy", state_dir=td)
            second = handle_completion(request, tenant="tenant-completion", namespace="legacy", state_dir=td)
            self.assertEqual(first["object"], "text_completion")
            self.assertIn("text", first["choices"][0])
            self.assertEqual(first["urp"]["cache"], "miss")
            self.assertEqual(second["urp"]["cache"], "exact_hit")
            self.assertNotEqual(first["urp"]["manifest_id"], second["urp"]["manifest_id"])

    def test_openai_compatible_provider_uses_live_http_endpoint_opt_in(self):
        seen = {}

        class ProviderHandler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("content-length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                seen["path"] = self.path
                seen["authorization"] = self.headers.get("authorization")
                seen["payload"] = payload
                body = json.dumps(
                    {
                        "id": "chatcmpl_live_test",
                        "object": "chat.completion",
                        "model": payload["model"],
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": "live provider response"},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 3, "completion_tokens": 3, "total_tokens": 6},
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A002
                return

        server = HTTPServer(("127.0.0.1", 0), ProviderHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                provider = OpenAICompatibleProvider.from_env(
                    {
                        "OPENAI_BASE_URL": f"http://{server.server_address[0]}:{server.server_address[1]}",
                        "OPENAI_API_KEY": "test-key",
                        "URP_OPENAI_MODEL": "provider-model",
                    }
                )
                response = handle_chat_completion(
                    {"model": "auto", "messages": [{"role": "user", "content": "hello"}]},
                    tenant="tenant-live-provider",
                    namespace="provider",
                    state_dir=td,
                    provider=provider,
                )
                manifest = default_manifest_store(td).get(response["urp"]["manifest_id"])
                self.assertEqual(seen["path"], "/v1/chat/completions")
                self.assertEqual(seen["authorization"], "Bearer test-key")
                self.assertEqual(seen["payload"]["model"], "provider-model")
                self.assertEqual(response["choices"][0]["message"]["content"], "live provider response")
                self.assertEqual(manifest.physical["compute_manifest"]["plan"]["selected_model"], "provider-model")
                self.assertTrue(manifest.telemetry["provider_called"])
        finally:
            server.shutdown()
            server.server_close()

    def test_ai_gateway_embedding_lifecycle_and_exact_cache_hit(self):
        with tempfile.TemporaryDirectory() as td:
            request = {"model": "mock-embedding", "input": "embed me", "urp": {"source_fingerprints": ["doc-v1"]}}
            first = handle_embeddings(request, tenant="tenant-embed", namespace="vectors", state_dir=td)
            second = handle_embeddings(request, tenant="tenant-embed", namespace="vectors", state_dir=td)
            self.assertEqual(first["object"], "list")
            self.assertIn("urp", first)
            self.assertEqual(first["urp"]["cache"], "miss")
            self.assertEqual(second["urp"]["cache"], "exact_hit")
            manifest = default_manifest_store(td).get(first["urp"]["manifest_id"])
            self.assertEqual(manifest.kind, WorkUnitKind.EMBEDDING_REQUEST)
            self.assertFalse(manifest.classification["raw_prompt_logged"])
            self.assertEqual(manifest.physical["cache_result"], "miss")
            validate_named_schema("compute_manifest", manifest.physical["compute_manifest"])
            second_manifest = default_manifest_store(td).get(second["urp"]["manifest_id"])
            validate_named_schema("compute_manifest", second_manifest.physical["compute_manifest"])
            self.assertFalse(second_manifest.physical["compute_manifest"]["result"]["large_model_called"])
            event_types = [event.event_type for event in default_ledger(td).query(work_unit_id=first["urp"]["work_unit_id"])]
            self.assertIn("work_unit.received", event_types)
            self.assertIn("policy.evaluated", event_types)
            self.assertIn("plan.created", event_types)
            self.assertIn("manifest.written", event_types)

    def test_ai_gateway_semantic_cache_is_policy_gated(self):
        with tempfile.TemporaryDirectory() as td:
            tenant = "tenant-ai-semantic"
            request = {
                "model": "auto",
                "messages": [
                    {"role": "system", "content": "source:vpn-v1"},
                    {"role": "user", "content": "Summarize VPN reset policy"},
                ],
                "urp": {"allow_semantic_cache": True},
            }
            first = handle_chat_completion(request, tenant=tenant, namespace="support", state_dir=td)
            semantic = handle_chat_completion({**request, "model": "different-model"}, tenant=tenant, namespace="support", state_dir=td)
            stale_source = {
                **request,
                "model": "another-model",
                "messages": [
                    {"role": "system", "content": "source:vpn-v2"},
                    {"role": "user", "content": "Summarize VPN reset policy"},
                ],
            }
            stale = handle_chat_completion(stale_source, tenant=tenant, namespace="support", state_dir=td)
            self.assertEqual(first["urp"]["cache"], "miss")
            self.assertEqual(semantic["urp"]["cache"], "semantic_hit")
            self.assertEqual(stale["urp"]["cache"], "miss")

    def test_context_compiler_dedupes_and_budgets(self):
        chunks = [ContextChunk("repeat", "a"), ContextChunk("repeat", "a"), ContextChunk("long text", "b")]
        compiled = compile_context(chunks, max_tokens=10)
        self.assertEqual(len(compiled.chunks), 2)
        self.assertEqual(len(compiled.removed_fingerprints), 1)

    def test_local_s3_put_head_get_range(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalS3Adapter(td, tenant="tenant-s3")
            put = adapter.put_object("bucket", "key", b"0123456789", metadata={"content-type": "text/plain"}, tags={"data_class": "demo"})
            self.assertEqual(adapter.get_object(put["manifest_id"]), b"0123456789")
            self.assertEqual(adapter.range_read(put["manifest_id"], 2, 5), b"234")
            head = adapter.head_object(put["manifest_id"])
            self.assertEqual(head["content_length"], 10)
            self.assertEqual(head["metadata"], {"content-type": "text/plain"})
            self.assertEqual(head["tags"], {"data_class": "demo"})
            listed = adapter.list_objects("bucket", "k")
            self.assertEqual(listed["count"], 1)
            self.assertEqual(listed["objects"][0]["key"], "key")
            denied = adapter.delete_object(put["manifest_id"], actor="tester")
            self.assertFalse(denied["deleted"])
            self.assertEqual(denied["reason"], "delete_disabled_by_default")
            tombstoned = adapter.delete_object(put["manifest_id"], actor="tester", allow_delete=True)
            self.assertTrue(tombstoned["deleted"])
            self.assertEqual(adapter.head_object(put["manifest_id"])["manifest_id"], put["manifest_id"])
            self.assertEqual(adapter.list_objects("bucket", "k")["count"], 0)
            self.assertEqual(adapter.list_objects("bucket", "k", include_tombstoned=True)["count"], 1)
            held = adapter.put_object("bucket", "held", b"held", tags={"legal_hold": "true"})
            held_delete = adapter.delete_object(held["manifest_id"], actor="tester", allow_delete=True)
            self.assertFalse(held_delete["deleted"])
            self.assertEqual(held_delete["reason"], "legal_hold")

    def test_local_s3_multipart_complete_and_abort(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalS3Adapter(td, tenant="tenant-s3")
            upload = adapter.create_multipart_upload("bucket", "multipart-key")
            adapter.upload_part(upload["upload_id"], 2, b"world")
            adapter.upload_part(upload["upload_id"], 1, b"hello ")
            completed = adapter.complete_multipart_upload(upload["upload_id"])
            self.assertEqual(completed["parts"], 2)
            self.assertEqual(adapter.get_object(completed["manifest_id"]), b"hello world")
            aborted = adapter.create_multipart_upload("bucket", "aborted-key")
            self.assertTrue(adapter.abort_multipart_upload(aborted["upload_id"])["aborted"])

    def test_posix_adapter_file_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "files"
            source = root / "input.txt"
            adapter = POSIXAdapter(Path(td) / "state", tenant="tenant-posix")
            put = adapter.write_file(source, b"posix payload", overwrite=False)
            self.assertTrue(put["accepted"])
            manifest_id = put["manifest_id"]
            plan = adapter.plan_file(source)
            self.assertEqual(plan["contract"], "exact_bytes")
            self.assertIn("score_components", plan["expected"])
            self.assertEqual(adapter.read_file(manifest_id), b"posix payload")
            restored = root / "restored.txt"
            result = adapter.rehydrate_file(manifest_id, restored)
            self.assertEqual(result["bytes"], len(b"posix payload"))
            self.assertEqual(restored.read_bytes(), b"posix payload")
            stat = adapter.stat_file(manifest_id)
            self.assertEqual(stat["content_length"], len(b"posix payload"))
            self.assertEqual(stat["path"], str(source))
            listing = adapter.list_dir(root)
            self.assertIn("input.txt", {row["name"] for row in listing["entries"]})
            with self.assertRaises(FileExistsError):
                adapter.put_file(source, b"again")
            with self.assertRaises(FileExistsError):
                adapter.rehydrate_file(manifest_id, restored)

    def test_local_mock_contract_adapters_are_rehydratable_and_external_free(self):
        with tempfile.TemporaryDirectory() as td:
            adapters = built_in_adapters()
            for name in ["sql", "lakehouse", "stream", "otlp", "training", "vector", "edge", "cicd"]:
                adapter = adapters[name]
                caps = adapter.capabilities()
                kind = WorkUnitKind(caps["kinds"][0])
                payload = {"adapter": name, "records": [{"id": 1, "value": f"{name}-payload"}]}
                planned = adapter.plan_work_unit(WorkUnit(kind, f"tenant-{name}", f"{name}://planned", payload, namespace=name))
                self.assertEqual(planned["contract"], "exact_bytes")
                result = adapter.submit_work_unit(kind, f"{name}://demo", payload, state_dir=td, tenant=f"tenant-{name}")
                self.assertTrue(result["accepted"], name)
                manifest = default_manifest_store(td).get(result["manifest_id"])
                self.assertEqual(manifest.physical["adapter"], name)
                self.assertFalse(manifest.physical["external_integrations_required"])
                self.assertEqual(rehydrate_manifest(result["manifest_id"], td), payload_to_bytes(payload))
                self.assertEqual(adapter.rehydrate(result["manifest_id"], state_dir=td), payload_to_bytes(payload))
                events = [event.event_type for event in default_ledger(td).query(work_unit_id=result["work_unit_id"])]
                self.assertIn("manifest.written", events)
                self.assertIn("adapter.mock.executed", events)
            with self.assertRaises(ValueError):
                adapters["sql"].submit_work_unit(WorkUnitKind.PROMPT_REQUEST, "sql://unsupported", {"q": "x"}, state_dir=td)

    def test_checkpoint_delta_store_reconstructs(self):
        with tempfile.TemporaryDirectory() as td:
            store = CheckpointDeltaStore(td, block_size=4)
            base = b"aaaabbbbcccc"
            target = b"aaaabbbbdddd"
            store.put_base("base", base)
            delta = store.put_delta("base", "target", target)
            self.assertGreater(delta["bytes_avoided"], 0)
            self.assertEqual(store.read("target"), target)

    def test_lakehouse_training_and_scheduler_local_reducers(self):
        lakehouse = recommend_compaction(
            [
                LakehouseFile("s3://table/dt=1/a.parquet", "dt=1", 1024, 10),
                LakehouseFile("s3://table/dt=1/b.parquet", "dt=1", 2048, 20),
                LakehouseFile("s3://table/dt=2/large.parquet", "dt=2", 1024 * 1024, 100),
            ],
            target_file_size=16 * 1024,
        )
        self.assertTrue(lakehouse.accepted)
        self.assertEqual(lakehouse.groups[0].files_avoided, 1)
        self.assertEqual(lakehouse.groups[0].verifier, "snapshot_equivalence")

        training = dedupe_training_samples(
            [
                TrainingSample("a", "same sample", {"source": "kb"}),
                TrainingSample("b", "same sample", {"source": "kb"}),
                TrainingSample("c", "new sample", {"source": "kb"}),
            ]
        )
        self.assertTrue(training.accepted)
        self.assertEqual(training.duplicate_map, {"b": "a"})
        self.assertGreater(training.bytes_avoided, 0)

        self.assertTrue(schedule(deadline_seconds=30, carbon_signal=0.99).run_now)
        with tempfile.TemporaryDirectory() as td:
            decision = SchedulerStore(td).submit(FlexibleJob("tenant-s", "batch_compute_job", deadline_seconds=3600, carbon_signal=0.95))
            self.assertFalse(decision.run_now)
            self.assertGreater(decision.shifted_seconds, 0)
            self.assertEqual(len(SchedulerStore(td).read()), 1)

            mock_result = execute_work_unit(WorkUnit(WorkUnitKind.TABLE_SNAPSHOT, "tenant-s", "lakehouse://table"), td)
            mock_events = [event.event_type for event in default_ledger(td).query(work_unit_id=mock_result.work_unit_id)]
            self.assertIn("work_unit.received", mock_events)
            self.assertIn("policy.evaluated", mock_events)
            self.assertIn("plan.created", mock_events)
            self.assertIn("adapter.mock.executed", mock_events)

    def test_savings_report(self):
        with tempfile.TemporaryDirectory() as td:
            execute_work_unit(WorkUnit(WorkUnitKind.BYTE_OBJECT, "tenant-r", "s3://b/k", b"abc" * 1000), td)
            report = savings_report(td, "tenant-r")
            self.assertEqual(report["manifest_count"], 1)
            self.assertGreater(report["bytes_in"], 0)
            self.assertIn("cache_hit_rate", report)
            dashboard = dashboard_report(td, "tenant-r")
            self.assertEqual(dashboard["summary"]["manifest_count"], 1)
            self.assertIn("executive", dashboard)
            self.assertIn("platform", dashboard)
            self.assertIn("ai", dashboard)
            self.assertIn("data", dashboard)
            self.assertIn("security", dashboard)
            explorer = manifest_explorer_report(td, tenant="tenant-r")
            self.assertEqual(explorer["manifest_count"], 1)
            self.assertEqual(explorer["by_kind"]["byte_object"], 1)
            self.assertEqual(explorer["rows"][0]["logical_ref"], "[redacted]")
            self.assertGreaterEqual(explorer["totals"]["logical_bytes"], 3000)

    def test_disaster_recovery_export_import_rehydrates(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            dst = Path(td) / "dst"
            archive = Path(td) / "backup.zip"
            data = b"restore me" * 1000
            result = execute_work_unit(WorkUnit(WorkUnitKind.BYTE_OBJECT, "tenant-dr", "s3://b/k", data), src)
            export_manifest = export_state(src, archive)
            self.assertTrue(archive.exists())
            self.assertGreater(len(export_manifest["files"]), 0)
            restore = import_state(archive, dst)
            self.assertTrue(restore["imported"])
            self.assertEqual(rehydrate_manifest(result.manifest_id, dst), data)

    def test_production_readiness_check(self):
        result = production_readiness_check()
        self.assertTrue(result.passed, result.to_dict())
        self.assertTrue(result.checks["manifest_persists_after_restart"])
        self.assertTrue(result.checks["exact_rehydration_after_restart"])
        self.assertTrue(result.checks["policy_change_audited"])
        self.assertTrue(result.checks["backup_integrity_detected"])
        self.assertTrue(result.checks["operator_manifest_declared"])
        self.assertTrue(result.checks["multi_region_topology_declared"])

    def test_policy_bundle_publish_and_rollback_are_audited(self):
        with tempfile.TemporaryDirectory() as td:
            store = PolicyBundleStore(td)
            first = store.publish(Path(__file__).resolve().parents[2] / "examples/policies/default_policy.yaml", actor="admin")
            second_bundle = dict(first["bundle"])
            second_bundle["metadata"] = dict(second_bundle["metadata"])
            second_bundle["metadata"]["version"] = "v2"
            second = store.publish(second_bundle, actor="admin")
            rolled = store.rollback(first["name"], first["version"], actor="admin")
            reloaded = store.reload(first["name"], actor="admin")
            self.assertEqual(rolled["version"], first["version"])
            self.assertEqual(reloaded["version"], first["version"])
            self.assertTrue(reloaded["record_hash_matches"])
            events = [e.event_type for e in default_ledger(td).read()]
            self.assertIn("policy.bundle.published", events)
            self.assertIn("policy.bundle.rolled_back", events)
            self.assertIn("policy.bundle.reloaded", events)
            self.assertEqual(store.active(first["name"])["version"], first["version"])
            self.assertEqual(second["version"], "v2")

    def test_local_kms_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            kms = LocalKMS(td)
            key = kms.create_key("manifest-fields")
            envelope = kms.encrypt(key.key_id, b"secret logical ref", aad=b"manifest")
            self.assertNotIn("secret", envelope["ciphertext"])
            self.assertEqual(kms.decrypt(envelope, aad=b"manifest"), b"secret logical ref")

    def test_cli_execute_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ)
            env["PYTHONPATH"] = "python"
            root = Path(__file__).resolve().parents[2]
            top_plan = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "plan", "--kind", "byte_object", "--input", "planned"],
                env=env,
                cwd=root,
            )
            top_plan_json = json.loads(top_plan)
            top_plan_events = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "ledger", "query", "--work-unit-id", top_plan_json["work_unit_id"]],
                env=env,
                cwd=root,
            )
            self.assertIn("plan.created", [row["event_type"] for row in json.loads(top_plan_events)])
            cmd = [sys.executable, "-m", "urp.cli", "--state-dir", td, "execute", "--kind", "byte_object", "--input", "hello"]
            out = subprocess.check_output(cmd, env=env, cwd=root)
            result = json.loads(out)
            self.assertTrue(result["accepted"])
            get = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "manifest", "get", result["manifest_id"]],
                env=env,
                cwd=root,
            )
            self.assertEqual(json.loads(get)["manifest_id"], result["manifest_id"])
            ranged = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "manifest", "rehydrate", result["manifest_id"], "--range", "1:4"],
                env=env,
                cwd=root,
            )
            self.assertEqual(ranged.decode("utf-8").strip(), "ell")
            filtered_events = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "ledger", "query", "--event-type", "manifest.written", "--event-types", "plan.created,policy.evaluated"],
                env=env,
                cwd=root,
            )
            filtered_types = {row["event_type"] for row in json.loads(filtered_events)}
            self.assertTrue(filtered_types.issubset({"manifest.written", "plan.created", "policy.evaluated"}))
            self.assertIn("manifest.written", filtered_types)
            report = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "report", "savings"],
                env=env,
                cwd=root,
            )
            self.assertGreaterEqual(json.loads(report)["manifest_count"], 1)
            dashboard = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "report", "dashboard"],
                env=env,
                cwd=root,
            )
            self.assertIn("executive", json.loads(dashboard))
            ai_conformance = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "conformance", "ai"],
                env=env,
                cwd=root,
            )
            self.assertTrue(json.loads(ai_conformance)["passed"])
            readiness = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "admin", "readiness"],
                env=env,
                cwd=root,
            )
            self.assertTrue(json.loads(readiness)["passed"])
            policy_path = root / "examples/policies/default_policy.yaml"
            policy_validate = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "policy", "validate", str(policy_path)],
                env=env,
                cwd=root,
            )
            policy_publish = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "policy", "publish", str(policy_path), "--actor", "cli-admin"],
                env=env,
                cwd=root,
            )
            policy_reload = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "policy", "reload", "--name", "default-safe", "--actor", "cli-admin"],
                env=env,
                cwd=root,
            )
            self.assertTrue(json.loads(policy_validate)["valid"])
            self.assertEqual(json.loads(policy_publish)["name"], "default-safe")
            self.assertEqual(json.loads(policy_reload)["name"], "default-safe")
            self.assertTrue(json.loads(policy_reload)["record_hash_matches"])
            gateway = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "gateway", "ai", "--provider", "mock"],
                env=env,
                cwd=root,
                timeout=5,
            )
            gateway_json = json.loads(gateway)
            self.assertIn("choices", gateway_json)
            self.assertIn("urp", gateway_json)
            plugin_packages = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "plugin", "conformance", "--all-packages"],
                env=env,
                cwd=root,
            )
            self.assertTrue(all(row["passed"] for row in json.loads(plugin_packages)))

            created = subprocess.check_output(
                [
                    sys.executable,
                    "-m",
                    "urp.cli",
                    "--state-dir",
                    td,
                    "work-unit",
                    "create",
                    "--kind",
                    "byte_object",
                    "--tenant",
                    "tenant-cli",
                    "--logical-ref",
                    "s3://cli/object",
                    "--input",
                    "cli-payload",
                ],
                env=env,
                cwd=root,
            )
            work_unit_id = json.loads(created)["work_unit_id"]
            planned = subprocess.check_output([sys.executable, "-m", "urp.cli", "--state-dir", td, "work-unit", "plan", work_unit_id], env=env, cwd=root)
            plan_events = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "ledger", "query", "--work-unit-id", work_unit_id],
                env=env,
                cwd=root,
            )
            executed = subprocess.check_output([sys.executable, "-m", "urp.cli", "--state-dir", td, "work-unit", "execute", work_unit_id], env=env, cwd=root)
            exported = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "manifest", "export", "--tenant", "tenant-cli"],
                env=env,
                cwd=root,
            )
            explored = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "manifest", "explore", "--tenant", "tenant-cli"],
                env=env,
                cwd=root,
            )
            logs = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "logs", "query", "--tenant", "tenant-cli", "--event-type", "manifest.written"],
                env=env,
                cwd=root,
            )
            planned_json = json.loads(planned)
            self.assertEqual(planned_json["work_unit_id"], work_unit_id)
            self.assertTrue((Path(td) / "plans" / f"{planned_json['plan_id']}.json").exists())
            self.assertIn("plan.created", [row["event_type"] for row in json.loads(plan_events)])
            self.assertTrue(json.loads(executed)["accepted"])
            manifest_export = json.loads(exported)
            self.assertEqual(manifest_export["manifest_count"], 1)
            self.assertEqual(manifest_export["manifests"][0]["logical_ref"], "[redacted]")
            self.assertEqual(json.loads(explored)["manifest_count"], 1)
            self.assertEqual(json.loads(explored)["rows"][0]["logical_ref"], "[redacted]")
            self.assertIn("manifest.written", [row["event_type"] for row in json.loads(logs)])

    def test_fastapi_semantic_cache_and_range_rehydrate(self):
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:  # pragma: no cover - optional dependency path
            self.skipTest(f"FastAPI test client unavailable: {exc}")
        with tempfile.TemporaryDirectory() as td:
            from urp.api import create_app

            client = TestClient(create_app(td, authenticator=_test_authenticator()))
            unauthenticated = client.get("/v1/models")
            self.assertEqual(unauthenticated.status_code, 401)
            self.assertEqual(unauthenticated.headers["cache-control"], "no-store")
            self.assertEqual(unauthenticated.headers["x-content-type-options"], "nosniff")
            client.headers.update({"authorization": f"Bearer {_ADMIN_API_KEY}"})
            invalid_wu = client.post(
                "/v1/work-units",
                json={"kind": "byte_object", "tenant": "", "logical_ref": "s3://b/invalid", "payload": "invalid"},
            )
            missing_manifest = client.get("/v1/manifests/mf_missing")
            self.assertEqual(invalid_wu.status_code, 400)
            self.assertEqual(invalid_wu.json()["error"]["code"], "schema_validation_failed")
            self.assertIn("non-empty", invalid_wu.json()["error"]["message"])
            self.assertEqual(missing_manifest.status_code, 404)
            self.assertEqual(missing_manifest.json()["error"]["code"], "not_found")
            created_wu = client.post(
                "/v1/work-units",
                json={"kind": "byte_object", "tenant": "tenant-api", "logical_ref": "s3://b/from-store", "payload": "stored"},
            )
            self.assertEqual(created_wu.status_code, 200)
            work_unit_id = created_wu.json()["work_unit_id"]
            stored_plan = client.post(f"/v1/work-units/{work_unit_id}/plan")
            stored_exec = client.post(f"/v1/work-units/{work_unit_id}/execute", json={"mode": "enforce"})
            self.assertEqual(stored_plan.status_code, 200)
            self.assertEqual(stored_plan.json()["work_unit_id"], work_unit_id)
            listed_plans = client.get("/v1/plans", params={"work_unit_id": work_unit_id})
            fetched_plan = client.get(f"/v1/plans/{stored_plan.json()['plan_id']}")
            inline_plan = client.post(
                "/v1/plans",
                json={"kind": "byte_object", "tenant": "tenant-api", "logical_ref": "s3://b/inline-plan", "payload": "planned"},
            )
            self.assertEqual(listed_plans.status_code, 200)
            self.assertTrue(any(row["plan_id"] == stored_plan.json()["plan_id"] for row in listed_plans.json()))
            self.assertEqual(fetched_plan.json()["work_unit_id"], work_unit_id)
            self.assertEqual(inline_plan.status_code, 200)
            self.assertTrue(inline_plan.json()["plan_id"].startswith("pl_"))
            plan_events = client.post("/v1/ledger/query", json={"work_unit_id": work_unit_id, "event_types": ["plan.created"]})
            inline_plan_events = client.post("/v1/ledger/query", json={"work_unit_id": inline_plan.json()["work_unit_id"], "event_types": ["plan.created"]})
            self.assertEqual(plan_events.status_code, 200)
            self.assertEqual(inline_plan_events.status_code, 200)
            self.assertTrue(plan_events.json())
            self.assertTrue(inline_plan_events.json())
            self.assertTrue(stored_exec.json()["accepted"])
            manifest_query = client.get("/v1/manifests", params={"logical_ref": "s3://b/from-store"})
            manifest_explore = client.get("/v1/manifests/explore", params={"tenant": "tenant-api"})
            manifest_export = client.post("/v1/manifests/export", json={"tenant": "tenant-api", "redacted": True})
            self.assertEqual(manifest_query.status_code, 200)
            self.assertEqual(manifest_explore.status_code, 200)
            self.assertGreaterEqual(len(manifest_query.json()), 1)
            self.assertGreaterEqual(manifest_explore.json()["manifest_count"], 1)
            self.assertEqual(manifest_explore.json()["rows"][0]["logical_ref"], "[redacted]")
            self.assertTrue(manifest_export.json()["redacted"])
            self.assertEqual(manifest_export.json()["manifests"][0]["logical_ref"], "[redacted]")

            executed = client.post(
                "/v1/work-units/execute",
                json={"kind": "byte_object", "tenant": "tenant-api", "logical_ref": "s3://b/k", "payload": "0123456789"},
            )
            self.assertEqual(executed.status_code, 200)
            manifest_id = executed.json()["manifest_id"]
            ranged = client.post(f"/v1/manifests/{manifest_id}/rehydrate", json={"range": {"start": 2, "end": 5}})
            self.assertEqual(ranged.status_code, 200)
            self.assertEqual(ranged.content, b"234")
            self.assertEqual(ranged.headers["cache-control"], "no-store")

            tenant = "tenant-api-semantic"
            chat = client.post(
                "/v1/chat/completions",
                json={
                    "model": "auto",
                    "messages": [{"role": "user", "content": "Summarize API reset policy"}],
                    "urp": {
                        "tenant": tenant,
                        "namespace": "support",
                        "allow_semantic_cache": True,
                        "source_fingerprints": ["source-api-v1"],
                    },
                },
            )
            self.assertEqual(chat.status_code, 200)
            completion = client.post(
                "/v1/completions",
                json={"model": "auto", "prompt": "Summarize API completion policy", "urp": {"tenant": tenant, "namespace": "support"}},
            )
            self.assertEqual(completion.status_code, 200)
            self.assertEqual(completion.json()["object"], "text_completion")
            self.assertIn("text", completion.json()["choices"][0])
            embedding = client.post(
                "/v1/embeddings",
                json={"model": "mock-embedding", "input": "embed via api", "urp": {"tenant": tenant, "namespace": "vectors", "source_fingerprints": ["source-api-v1"]}},
            )
            self.assertEqual(embedding.status_code, 200)
            self.assertEqual(embedding.json()["object"], "list")
            self.assertIn("urp", embedding.json())
            embedding_manifest = client.get(f"/v1/manifests/{embedding.json()['urp']['manifest_id']}")
            self.assertEqual(embedding_manifest.status_code, 200)
            self.assertEqual(embedding_manifest.json()["kind"], "embedding_request")
            denied = client.post(
                "/v1/cache/semantic/lookup",
                json={"tenant": tenant, "namespace": "support", "text": "Summarize API reset policy", "source_fingerprints": ["source-api-v1"], "allow_semantic_cache": False},
            )
            self.assertEqual(denied.json()["allowed"], False)
            lookup = client.post(
                "/v1/cache/semantic/lookup",
                json={
                    "tenant": tenant,
                    "namespace": "support",
                    "text": "Summarize API reset policy",
                    "source_fingerprints": ["source-api-v1"],
                    "allow_semantic_cache": True,
                },
            )
            self.assertEqual(lookup.status_code, 200)
            self.assertEqual(lookup.json()["allowed"], True)
            self.assertEqual(lookup.json()["hit"], True)

            rejected_cache = client.post(
                "/v1/cache/store",
                json={
                    "key": "ck_api",
                    "tenant": "tenant-api",
                    "namespace": "default",
                    "value": {"answer": "x"},
                    "source_fingerprints": ["src1"],
                    "verification": {"type": "json_shape", "required_keys": ["missing"]},
                },
            )
            stored_cache = client.post(
                "/v1/cache/store",
                json={
                    "key": "ck_api",
                    "tenant": "tenant-api",
                    "namespace": "default",
                    "value": {"answer": "x"},
                    "source_fingerprints": ["src1"],
                    "verification": {"type": "json_shape", "required_keys": ["answer"]},
                },
            )
            exact_lookup = client.post(
                "/v1/cache/exact/lookup",
                json={"key": "ck_api", "tenant": "tenant-api", "namespace": "default", "source_fingerprints": ["src1"]},
            )
            self.assertEqual(rejected_cache.status_code, 400)
            self.assertEqual(rejected_cache.json()["error"]["code"], "verifier_failed")
            self.assertTrue(stored_cache.json()["stored"])
            self.assertTrue(exact_lookup.json()["hit"])

            s3_put = client.post(
                "/v1/s3/objects",
                json={
                    "bucket": "bucket",
                    "key": "api-key",
                    "body_text": "0123456789",
                    "metadata": {"content-type": "text/plain"},
                    "tags": {"data_class": "api-demo"},
                },
            )
            s3_head = client.post("/v1/s3/objects/head", json={"manifest_id": s3_put.json()["manifest_id"]})
            s3_get = client.post("/v1/s3/objects/get", json={"manifest_id": s3_put.json()["manifest_id"]})
            s3_range = client.post("/v1/s3/objects/range", json={"manifest_id": s3_put.json()["manifest_id"], "start": 2, "end": 5})
            s3_list = client.post("/v1/s3/objects/list", json={"bucket": "bucket", "prefix": "api"})
            s3_delete = client.post("/v1/s3/objects/delete", json={"manifest_id": s3_put.json()["manifest_id"], "actor": "api"})
            s3_deleted = client.post("/v1/s3/objects/delete", json={"manifest_id": s3_put.json()["manifest_id"], "actor": "api", "allow_delete": True})
            s3_list_after_delete = client.post("/v1/s3/objects/list", json={"bucket": "bucket", "prefix": "api"})
            s3_list_tombstoned = client.post("/v1/s3/objects/list", json={"bucket": "bucket", "prefix": "api", "include_tombstoned": True})
            self.assertEqual(s3_head.json()["content_length"], 10)
            self.assertEqual(s3_head.json()["metadata"], {"content-type": "text/plain"})
            self.assertEqual(s3_head.json()["tags"], {"data_class": "api-demo"})
            self.assertEqual(s3_get.content, b"0123456789")
            self.assertEqual(s3_range.content, b"234")
            self.assertGreaterEqual(s3_list.json()["count"], 1)
            self.assertFalse(s3_delete.json()["deleted"])
            self.assertTrue(s3_deleted.json()["deleted"])
            self.assertEqual(s3_list_after_delete.json()["count"], 0)
            self.assertEqual(s3_list_tombstoned.json()["count"], 1)

            upload = client.post("/v1/s3/multipart/create", json={"bucket": "bucket", "key": "api-multipart"}).json()
            client.post("/v1/s3/multipart/part", json={"upload_id": upload["upload_id"], "part_number": 2, "body_text": "world"})
            client.post("/v1/s3/multipart/part", json={"upload_id": upload["upload_id"], "part_number": 1, "body_text": "hello "})
            completed = client.post("/v1/s3/multipart/complete", json={"upload_id": upload["upload_id"]}).json()
            completed_get = client.post("/v1/s3/objects/get", json={"manifest_id": completed["manifest_id"]})
            aborted = client.post("/v1/s3/multipart/create", json={"bucket": "bucket", "key": "api-abort"}).json()
            abort_result = client.post("/v1/s3/multipart/abort", json={"upload_id": aborted["upload_id"]})
            self.assertEqual(completed["parts"], 2)
            self.assertEqual(completed_get.content, b"hello world")
            self.assertTrue(abort_result.json()["aborted"])

            scheduled = client.post(
                "/v1/scheduler/submit",
                json={"tenant": "tenant-api", "deadline_seconds": 3600, "estimated_runtime_seconds": 120, "carbon_signal": 0.95},
            )
            jobs = client.get("/v1/scheduler/jobs")
            self.assertEqual(scheduled.status_code, 200)
            self.assertFalse(scheduled.json()["run_now"])
            self.assertEqual(len(jobs.json()), 1)

            ledger_stream = client.get("/v1/ledger/stream", params={"tenant": "tenant-api", "limit": 3})
            log_query = client.post("/v1/logs/query", json={"tenant": "tenant-api", "event_types": ["manifest.written"], "limit": 2})
            self.assertEqual(ledger_stream.status_code, 200)
            self.assertEqual(log_query.status_code, 200)
            self.assertIn("text/event-stream", ledger_stream.headers["content-type"])
            self.assertIn("data: ", ledger_stream.text)
            self.assertTrue(any(row["event_type"] == "manifest.written" for row in log_query.json()))
            dashboard = client.get("/v1/reports/dashboard", params={"tenant": "tenant-api"})
            ai_conformance = client.get("/v1/conformance/ai")
            readiness = client.get("/v1/admin/readiness")
            platform_profiles = client.get("/v1/platforms")
            platform_readiness = client.get("/v1/platforms/readiness")
            platform_live = client.get("/v1/platforms/readiness", params={"target": "aws", "require_live": True})
            platform_matrix = client.get("/v1/platforms/matrix")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn("security", dashboard.json())
            self.assertEqual(ai_conformance.status_code, 200)
            self.assertTrue(ai_conformance.json()["passed"])
            self.assertEqual(readiness.status_code, 200)
            self.assertTrue(readiness.json()["passed"])
            self.assertEqual(platform_profiles.status_code, 200)
            self.assertIn("aws", {row["name"] for row in platform_profiles.json()})
            self.assertIn("azure", {row["name"] for row in platform_profiles.json()})
            self.assertEqual(platform_readiness.status_code, 200)
            self.assertTrue(all(row["contract_ready"] for row in platform_readiness.json()))
            self.assertEqual(platform_live.status_code, 200)
            self.assertTrue(platform_live.json()["contract_ready"])
            self.assertFalse(platform_live.json()["live_ready"])
            self.assertEqual(platform_matrix.status_code, 200)
            self.assertEqual(platform_matrix.json()["contract_ready_count"], platform_matrix.json()["platform_count"])
            bundle = {
                "apiVersion": "urp.dev/v1",
                "kind": "ReductionPolicy",
                "metadata": {"name": "api-policy", "version": "v1"},
                "spec": {"defaults": {"contract": "exact_bytes"}, "rules": []},
            }
            published_policy = client.post("/v1/policies/bundles", json={"bundle": bundle, "actor": "api-admin"})
            reloaded_policy = client.post("/v1/policies/bundles/api-policy/reload", json={"actor": "api-admin"})
            self.assertEqual(published_policy.status_code, 200)
            self.assertEqual(reloaded_policy.status_code, 200)
            self.assertEqual(reloaded_policy.json()["version"], "v1")
            self.assertTrue(reloaded_policy.json()["record_hash_matches"])

    def test_local_services_start_and_handle_control_requests(self):
        with tempfile.TemporaryDirectory() as td:
            specs = service_specs()
            self.assertEqual(set(specs), {"control-plane", "gateway-ai", "gateway-s3", "worker", "scheduler"})
            self.assertTrue(service_health("control-plane", td)["ok"])
            server = create_service_server("control-plane", "127.0.0.1", 0, td, authenticator=_test_authenticator())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://{server.server_address[0]}:{server.server_address[1]}"
                health = _http_json(base + "/healthz")
                self.assertEqual(health["service"]["name"], "control-plane")
                self.assertIn("/v1/policies/evaluate", set(health["service"]["endpoints"]))
                self.assertIn("/v1/cache/store", set(health["service"]["endpoints"]))
                self.assertIn("/v1/admin/backup", set(health["service"]["endpoints"]))
                self.assertIn("/v1/ledger/stream", set(health["service"]["endpoints"]))
                self.assertIn("/v1/logs/query", set(health["service"]["endpoints"]))
                self.assertIn("/v1/plans", set(health["service"]["endpoints"]))
                self.assertIn("/v1/manifests/explore", set(health["service"]["endpoints"]))
                self.assertIn("/v1/reports/dashboard", set(health["service"]["endpoints"]))
                self.assertIn("/v1/conformance/ai", set(health["service"]["endpoints"]))
                self.assertIn("/v1/admin/readiness", set(health["service"]["endpoints"]))
                self.assertIn("/v1/platforms/readiness", set(health["service"]["endpoints"]))
                self.assertIn("/v1/policies/bundles/{name}/reload", set(health["service"]["endpoints"]))
                unauthenticated = _http_json_status(base + "/v1/manifests", api_key=None)
                self.assertEqual(unauthenticated[0], 401)
                self.assertEqual(unauthenticated[1]["error"]["code"], "authentication_required")
                invalid_work_unit = _http_json_status(
                    base + "/v1/work-units",
                    {"kind": "byte_object", "tenant": "", "logical_ref": "s3://b/invalid", "payload": "invalid"},
                )
                missing_manifest = _http_json_status(base + "/v1/manifests/mf_missing")
                self.assertEqual(invalid_work_unit[0], 400)
                self.assertEqual(invalid_work_unit[1]["error"]["code"], "schema_validation_failed")
                self.assertIn("non-empty", invalid_work_unit[1]["error"]["message"])
                self.assertEqual(missing_manifest[0], 404)
                self.assertEqual(missing_manifest[1]["error"]["code"], "not_found")
                created = _http_json(
                    base + "/v1/work-units",
                    {"kind": "byte_object", "tenant": "tenant-svc", "logical_ref": "s3://b/stored", "payload": "stored"},
                )
                stored_plan = _http_json(base + f"/v1/work-units/{created['work_unit_id']}/plan", {})
                stored_exec = _http_json(base + f"/v1/work-units/{created['work_unit_id']}/execute", {"mode": "enforce"})
                self.assertEqual(stored_plan["work_unit_id"], created["work_unit_id"])
                plan_get = _http_json(base + f"/v1/plans/{stored_plan['plan_id']}")
                plan_list = _http_json(base + f"/v1/plans?work_unit_id={created['work_unit_id']}")
                inline_stored_plan = _http_json(
                    base + "/v1/plans",
                    {"kind": "byte_object", "tenant": "tenant-svc", "logical_ref": "s3://b/plan-only", "payload": "plan-only"},
                )
                self.assertEqual(plan_get["plan_id"], stored_plan["plan_id"])
                self.assertTrue(any(row["plan_id"] == stored_plan["plan_id"] for row in plan_list))
                self.assertTrue(inline_stored_plan["plan_id"].startswith("pl_"))
                service_plan_events = _http_json(base + "/v1/ledger/query", {"work_unit_id": created["work_unit_id"], "event_types": ["plan.created"]})
                inline_service_plan_events = _http_json(base + "/v1/ledger/query", {"work_unit_id": inline_stored_plan["work_unit_id"], "event_types": ["plan.created"]})
                self.assertTrue(service_plan_events)
                self.assertTrue(inline_service_plan_events)
                self.assertTrue(stored_exec["accepted"])
                viewer_manifest = _http_json(
                    base + f"/v1/manifests/{stored_exec['manifest_id']}",
                    api_key=_VIEWER_API_KEY,
                )
                self.assertEqual(viewer_manifest["logical_ref"], "[redacted]")
                self.assertTrue(all("ref" not in segment for segment in viewer_manifest["physical"]["segments"]))
                rehydrated = _http_bytes(base + f"/v1/manifests/{stored_exec['manifest_id']}/rehydrate", {})
                ranged_rehydrated = _http_bytes(
                    base + f"/v1/manifests/{stored_exec['manifest_id']}/rehydrate",
                    {"range": {"start": 1, "end": 4}},
                )
                self.assertEqual(rehydrated, b"stored")
                self.assertEqual(ranged_rehydrated, b"tor")
                plan = _http_json(
                    base + "/v1/work-units/plan",
                    {"kind": "byte_object", "tenant": "tenant-svc", "logical_ref": "s3://b/k", "payload": "hello"},
                )
                self.assertEqual(plan["contract"], "exact_bytes")
                executed = _http_json(
                    base + "/v1/work-units/execute",
                    {"kind": "byte_object", "tenant": "tenant-svc", "logical_ref": "s3://b/k", "payload": "hello"},
                )
                self.assertTrue(executed["accepted"])
                savings = _http_json(base + "/v1/reports/savings?tenant=tenant-svc")
                manifest_explore = _http_json(base + "/v1/manifests/explore?tenant=tenant-svc")
                dashboard = _http_json(base + "/v1/reports/dashboard?tenant=tenant-svc")
                traces = _http_json(base + "/v1/traces/query", {"trace_id": created["trace_id"]})
                logs = _http_json(base + "/v1/logs/query", {"tenant": "tenant-svc", "event_types": ["manifest.written"], "limit": 3})
                ledger_stream = _http_text(base + "/v1/ledger/stream?tenant=tenant-svc&limit=5")
                route_feedback = _http_json(base + "/v1/routes/feedback")
                adapter_conformance = _http_json(base + "/v1/adapters/conformance")
                ai_conformance = _http_json(base + "/v1/conformance/ai")
                readiness = _http_json(base + "/v1/admin/readiness")
                platform_profiles = _http_json(base + "/v1/platforms")
                platform_readiness = _http_json(base + "/v1/platforms/readiness")
                platform_live = _http_json(base + "/v1/platforms/readiness?target=aws&require_live=true")
                platform_matrix = _http_json(base + "/v1/platforms/matrix")
                self.assertGreaterEqual(savings["manifest_count"], 2)
                self.assertGreaterEqual(manifest_explore["manifest_count"], 2)
                self.assertEqual(manifest_explore["rows"][0]["logical_ref"], "[redacted]")
                self.assertEqual(dashboard["summary"]["tenant"], "tenant-svc")
                self.assertIn("urp.manifest.write", {row["name"] for row in traces})
                self.assertTrue(any(row["event_type"] == "manifest.written" for row in logs))
                self.assertIn("data: ", ledger_stream)
                self.assertIn("tenant-svc", ledger_stream)
                self.assertIsInstance(route_feedback, dict)
                self.assertTrue(any(row["name"] == "s3" and row["passed"] for row in adapter_conformance))
                self.assertTrue(ai_conformance["passed"])
                self.assertTrue(readiness["passed"])
                self.assertIn("gcp", {row["name"] for row in platform_profiles})
                self.assertTrue(all(row["contract_ready"] for row in platform_readiness))
                self.assertTrue(platform_live["contract_ready"])
                self.assertFalse(platform_live["live_ready"])
                self.assertEqual(platform_matrix["contract_ready_count"], platform_matrix["platform_count"])
                policy = _http_json(
                    base + "/v1/policies/evaluate",
                    {"kind": "byte_object", "tenant": "tenant-svc", "logical_ref": "s3://b/k", "policy_context": {"legal_hold": True}},
                )
                self.assertEqual(policy["contract"], "exact_bytes")
                self.assertIn("delete", policy["denied_actions"])
                validated = _http_json(
                    base + "/v1/policies/validate",
                    {
                        "apiVersion": "urp.dev/v1",
                        "kind": "ReductionPolicy",
                        "metadata": {"name": "svc-policy"},
                        "spec": {"defaults": {"contract": "exact_bytes"}, "rules": []},
                    },
                )
                self.assertTrue(validated["valid"])
                bundle = {
                    "apiVersion": "urp.dev/v1",
                    "kind": "ReductionPolicy",
                    "metadata": {"name": "svc-policy", "version": "v1"},
                    "spec": {
                        "defaults": {"contract": "exact_bytes", "semanticReduction": "deny"},
                        "rules": [
                            {
                                "name": "semantic-cache",
                                "match": {"kind": "prompt_request"},
                                "contract": "semantic",
                                "allow": {"transforms": ["semantic_cache_enforce"]},
                                "require": {"verifiers": ["source_fingerprint_match"]},
                            }
                        ],
                    },
                }
                published_policy = _http_json(base + "/v1/policies/bundles", {"bundle": bundle, "actor": "svc-admin"})
                listed_policies = _http_json(base + "/v1/policies/bundles")
                rolled_policy = _http_json(base + "/v1/policies/bundles/svc-policy/rollback", {"version": "v1", "actor": "svc-admin"})
                reloaded_policy = _http_json(base + "/v1/policies/bundles/svc-policy/reload", {"actor": "svc-admin"})
                self.assertEqual(published_policy["name"], "svc-policy")
                self.assertTrue(any(row["name"] == "svc-policy" for row in listed_policies))
                self.assertEqual(rolled_policy["version"], "v1")
                self.assertEqual(reloaded_policy["version"], "v1")
                self.assertTrue(reloaded_policy["record_hash_matches"])
                plugin = _plugin_descriptor("svc-plugin")
                registered_plugin = _http_json(base + "/v1/plugins/register", {"descriptor": plugin, "actor": "svc-admin"})
                listed_plugins = _http_json(base + "/v1/plugins")
                kms_key = _http_json(base + "/v1/kms/keys", {"purpose": "svc-test"})
                backup_path = str(Path(td) / "svc-backup.zip")
                backup = _http_json(base + "/v1/admin/backup", {"output": backup_path})
                restore = _http_json(base + "/v1/admin/restore", {"archive": backup_path, "replace": False})
                self.assertEqual(registered_plugin["name"], "svc-plugin")
                self.assertTrue(any(row["name"] == "svc-plugin" for row in listed_plugins))
                self.assertTrue(kms_key["key_id"].startswith("key_"))
                self.assertTrue(Path(backup["archive"]).exists())
                self.assertTrue(restore["imported"])
                rejected_cache = _http_json_status(
                    base + "/v1/cache/store",
                    {
                        "key": "ck_svc",
                        "tenant": "tenant-svc",
                        "namespace": "default",
                        "value": {"answer": "x"},
                        "source_fingerprints": ["src1"],
                        "verification": {"type": "json_shape", "required_keys": ["missing"]},
                    },
                )
                self.assertEqual(rejected_cache[0], 400)
                self.assertEqual(rejected_cache[1]["error"]["code"], "verifier_failed")
                stored_cache = _http_json(
                    base + "/v1/cache/store",
                    {
                        "key": "ck_svc",
                        "tenant": "tenant-svc",
                        "namespace": "default",
                        "value": {"answer": "x"},
                        "source_fingerprints": ["src1"],
                        "verification": {"type": "json_shape", "required_keys": ["answer"]},
                    },
                )
                self.assertTrue(stored_cache["stored"])
                exact_hit = _http_json(
                    base + "/v1/cache/exact/lookup",
                    {"key": "ck_svc", "tenant": "tenant-svc", "namespace": "default", "source_fingerprints": ["src1"]},
                )
                cross_tenant_denied = _http_json_status(
                    base + "/v1/cache/exact/lookup",
                    {"key": "ck_svc", "tenant": "other-tenant", "namespace": "default", "source_fingerprints": ["src1"]},
                    api_key=_GATEWAY_API_KEY,
                )
                stale_source_miss = _http_json(
                    base + "/v1/cache/exact/lookup",
                    {"key": "ck_svc", "tenant": "tenant-svc", "namespace": "default", "source_fingerprints": ["src2"]},
                )
                self.assertTrue(exact_hit["hit"])
                self.assertEqual(cross_tenant_denied[0], 403)
                self.assertEqual(cross_tenant_denied[1]["error"]["code"], "tenant_mismatch")
                self.assertFalse(stale_source_miss["hit"])
                semantic_denied = _http_json(
                    base + "/v1/cache/semantic/lookup",
                    {"tenant": "tenant-svc", "namespace": "support", "text": "reset vpn", "source_fingerprints": ["src1"], "allow_semantic_cache": False},
                )
                semantic_allowed = _http_json(
                    base + "/v1/cache/semantic/lookup",
                    {
                        "tenant": "tenant-svc",
                        "namespace": "support",
                        "text": "reset vpn",
                        "source_fingerprints": ["src1"],
                        "allow_semantic_cache": True,
                        "policy_bundle_id": "svc-policy",
                    },
                )
                self.assertFalse(semantic_denied["allowed"])
                self.assertTrue(semantic_allowed["allowed"])
                auth_allowed = _http_json(
                    base + "/v1/auth/check",
                    {"tenant": "tenant-svc", "action": "manifest:read"},
                    api_key=_VIEWER_API_KEY,
                )
                auth_denied = _http_json_status(
                    base + "/v1/auth/check",
                    {"tenant": "tenant-svc", "action": "work_unit:write"},
                    api_key=_VIEWER_API_KEY,
                )
                self.assertTrue(auth_allowed["allowed"])
                self.assertEqual(auth_denied[0], 403)
                self.assertFalse(auth_denied[1]["allowed"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_ai_gateway_service_completion_embeddings_and_models(self):
        with tempfile.TemporaryDirectory() as td:
            server = create_service_server("gateway-ai", "127.0.0.1", 0, td, authenticator=_test_authenticator())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://{server.server_address[0]}:{server.server_address[1]}"
                health = _http_json(base + "/healthz")
                self.assertIn("/v1/completions", set(health["service"]["endpoints"]))
                first = _http_json(base + "/v1/completions", {"model": "auto", "prompt": "Summarize service completion"})
                second = _http_json(base + "/v1/completions", {"model": "auto", "prompt": "Summarize service completion"})
                embeddings = _http_json(base + "/v1/embeddings", {"input": "embed me"})
                models = _http_json(base + "/v1/models")
                self.assertEqual(first["object"], "text_completion")
                self.assertEqual(first["urp"]["cache"], "miss")
                self.assertEqual(second["urp"]["cache"], "exact_hit")
                self.assertEqual(embeddings["object"], "list")
                self.assertIn("urp", embeddings)
                self.assertEqual(default_manifest_store(td).get(embeddings["urp"]["manifest_id"]).kind, WorkUnitKind.EMBEDDING_REQUEST)
                self.assertTrue(any(row["id"] == "frontier" for row in models["data"]))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_local_s3_gateway_service_put_get_range(self):
        with tempfile.TemporaryDirectory() as td:
            server = create_service_server("gateway-s3", "127.0.0.1", 0, td, authenticator=_test_authenticator())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://{server.server_address[0]}:{server.server_address[1]}"
                health = _http_json(base + "/healthz")
                self.assertIn("/v1/s3/objects/get", set(health["service"]["endpoints"]))
                self.assertIn("/v1/s3/multipart/create", set(health["service"]["endpoints"]))
                put = _http_json(
                    base + "/v1/s3/objects",
                    {
                        "bucket": "bucket",
                        "key": "key",
                        "body_text": "0123456789",
                        "metadata": {"content-type": "text/plain"},
                        "tags": {"data_class": "svc-demo"},
                    },
                )
                head = _http_json(base + "/v1/s3/objects/head", {"manifest_id": put["manifest_id"]})
                got = _http_bytes(base + "/v1/s3/objects/get", {"manifest_id": put["manifest_id"]})
                ranged = _http_bytes(base + "/v1/s3/objects/range", {"manifest_id": put["manifest_id"], "start": 2, "end": 5})
                listed = _http_json(base + "/v1/s3/objects/list", {"bucket": "bucket", "prefix": "k"})
                deleted = _http_json(base + "/v1/s3/objects/delete", {"manifest_id": put["manifest_id"], "actor": "svc"})
                tombstoned = _http_json(base + "/v1/s3/objects/delete", {"manifest_id": put["manifest_id"], "actor": "svc", "allow_delete": True})
                listed_after_delete = _http_json(base + "/v1/s3/objects/list", {"bucket": "bucket", "prefix": "k"})
                listed_tombstoned = _http_json(base + "/v1/s3/objects/list", {"bucket": "bucket", "prefix": "k", "include_tombstoned": True})
                self.assertEqual(head["content_length"], 10)
                self.assertEqual(head["metadata"], {"content-type": "text/plain"})
                self.assertEqual(head["tags"], {"data_class": "svc-demo"})
                self.assertEqual(got, b"0123456789")
                self.assertEqual(ranged, b"234")
                self.assertEqual(listed["count"], 1)
                self.assertFalse(deleted["deleted"])
                self.assertTrue(tombstoned["deleted"])
                self.assertEqual(listed_after_delete["count"], 0)
                self.assertEqual(listed_tombstoned["count"], 1)
                upload = _http_json(base + "/v1/s3/multipart/create", {"bucket": "bucket", "key": "multipart-key"})
                _http_json(base + "/v1/s3/multipart/part", {"upload_id": upload["upload_id"], "part_number": 1, "body_text": "hello "})
                _http_json(base + "/v1/s3/multipart/part", {"upload_id": upload["upload_id"], "part_number": 2, "body_text": "world"})
                completed = _http_json(base + "/v1/s3/multipart/complete", {"upload_id": upload["upload_id"]})
                completed_get = _http_bytes(base + "/v1/s3/objects/get", {"manifest_id": completed["manifest_id"]})
                aborted = _http_json(base + "/v1/s3/multipart/create", {"bucket": "bucket", "key": "aborted-key"})
                abort_result = _http_json(base + "/v1/s3/multipart/abort", {"upload_id": aborted["upload_id"]})
                self.assertEqual(completed["parts"], 2)
                self.assertEqual(completed_get, b"hello world")
                self.assertTrue(abort_result["aborted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_cli_service_list_and_health(self):
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ)
            env["PYTHONPATH"] = "python"
            root = Path(__file__).resolve().parents[2]
            listed = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "service", "list"],
                env=env,
                cwd=root,
            )
            self.assertIn("control-plane", {row["name"] for row in json.loads(listed)})
            health = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "service", "health", "--name", "scheduler"],
                env=env,
                cwd=root,
            )
            self.assertTrue(json.loads(health)["ok"])
            platform_matrix = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "platform", "matrix"],
                env=env,
                cwd=root,
            )
            matrix = json.loads(platform_matrix)
            self.assertEqual(matrix["contract_ready_count"], matrix["platform_count"])
            platform_live = subprocess.check_output(
                [sys.executable, "-m", "urp.cli", "--state-dir", td, "platform", "validate", "--target", "aws", "--require-live"],
                env=env,
                cwd=root,
            )
            live = json.loads(platform_live)
            self.assertTrue(live["contract_ready"])
            self.assertFalse(live["live_ready"])


if __name__ == "__main__":
    unittest.main()


def _http_json(url: str, payload: dict | None = None, *, api_key: str | None = _ADMIN_API_KEY) -> dict:
    with urllib.request.urlopen(_http_request(url, payload, api_key), timeout=5) as response:
        return json.loads(response.read())


def _http_json_status(
    url: str,
    payload: dict | None = None,
    *,
    api_key: str | None = _ADMIN_API_KEY,
) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(_http_request(url, payload, api_key), timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _http_bytes(url: str, payload: dict | None = None, *, api_key: str | None = _ADMIN_API_KEY) -> bytes:
    with urllib.request.urlopen(_http_request(url, payload, api_key), timeout=5) as response:
        return response.read()


def _http_text(url: str, *, api_key: str | None = _ADMIN_API_KEY) -> str:
    with urllib.request.urlopen(_http_request(url, None, api_key), timeout=5) as response:
        return response.read().decode("utf-8")


def _http_request(url: str, payload: dict | None, api_key: str | None) -> urllib.request.Request:
    headers = {"accept": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    if payload is None:
        return urllib.request.Request(url, headers=headers, method="GET")
    headers["content-type"] = "application/json"
    return urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
