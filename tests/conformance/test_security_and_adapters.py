import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from urp.adapters import built_in_adapters, validate_plugin_descriptor
from urp.advanced import advanced_reducer_specs, evaluate_reducer, reducer_conformance, semantic_cache_placeholder
from urp.auth import APIKeyAuthenticator, LocalAuthorizer, Principal, principal_from_api_key
from urp.cache import CacheEntry, URPCache
from urp.conformance import ai_gateway_conformance
from urp.contracts import Contract, WorkUnit, WorkUnitKind
from urp.errors import verifier_failed
from urp.ledger import default_ledger
from urp.live_adapters import AWSS3Config, AWSS3ObjectAdapter, live_adapter_readiness
from urp.log_templates import extract_log_template, group_log_templates
from urp.metrics import default_metric_names
from urp.policy import audit_policy_override, evaluate_policy
from urp.plugins import PluginRegistry, adapter_conformance, discover_plugin_packages, plugin_package_conformance
from urp.release import build_release_manifest, verify_release_manifest, write_release_manifest
from urp.spec_validation import validate_api_specs
from urp.verifiers import VerificationResult


def _plugin_descriptor(entrypoint_sha256: str = "0" * 64) -> dict:
    return {
        "api_version": "urp.plugin.v1",
        "name": "local-transform",
        "version": "0.1.0",
        "category": "transforms",
        "capabilities": ["transform"],
        "contracts": ["exact_bytes"],
        "trust_level": "local",
        "entrypoint": "src/plugin.py",
        "entrypoint_sha256": entrypoint_sha256,
        "network_access": False,
        "operations": ["transform"],
        "default_enabled": False,
    }


class SecurityAndConformanceTests(unittest.TestCase):
    def test_legal_hold_blocks_delete_and_semantic(self):
        wu = WorkUnit(WorkUnitKind.BYTE_OBJECT, "t", "s3://b/k", policy_context={"legal_hold": True})
        decision = evaluate_policy(wu)
        self.assertEqual(decision.contract, Contract.EXACT_BYTES)
        self.assertIn("delete", decision.denied_actions)
        self.assertIn("semantic_summary", decision.denied_actions)

    def test_exact_contract_blocks_semantic_transform(self):
        wu = WorkUnit(WorkUnitKind.BYTE_OBJECT, "t", "s3://b/k")
        decision = evaluate_policy(wu)
        self.assertIn("semantic_cache_lookup", decision.denied_actions)

    def test_cache_source_fingerprint_checks(self):
        cache = URPCache()
        key = cache.exact_key("t", "app", {"q": "x"}, {"src1"})
        cache.put(CacheEntry(key, "t", "app", "answer", {"src1"}, True))
        self.assertIsNone(cache.get(key, "t", "app", {"src2"}))

    def test_plugin_descriptor_validation(self):
        self.assertFalse(validate_plugin_descriptor({"name": "bad"}).accepted)
        self.assertFalse(validate_plugin_descriptor(_plugin_descriptor() | {"capabilities": []}).accepted)
        self.assertTrue(validate_plugin_descriptor(_plugin_descriptor()).accepted)

    def test_advanced_reducer_disabled_without_policy_and_verifier(self):
        wu = WorkUnit(WorkUnitKind.PROMPT_REQUEST, "t", "app://q", requested_contract=Contract.SEMANTIC)
        decision = semantic_cache_placeholder(wu)
        self.assertFalse(decision.enabled)
        gated = WorkUnit(
            WorkUnitKind.PROMPT_REQUEST,
            "t",
            "app://q",
            requested_contract=Contract.SEMANTIC,
            policy_context={"allow_semantic_cache": True, "verifier": "source_fingerprint_match"},
        )
        self.assertFalse(semantic_cache_placeholder(gated).enabled)
        enabled = semantic_cache_placeholder(
            gated,
            [VerificationResult(True, "source_fingerprint_match@1", "sources_match")],
        )
        self.assertTrue(enabled.enabled)
        self.assertEqual(enabled.required_verifier, "source_fingerprint_match")
        self.assertTrue(enabled.rollback)

    def test_advanced_reducer_specs_have_gates_benchmarks_and_rollback(self):
        conformance = reducer_conformance()
        self.assertGreaterEqual(len(conformance), 6)
        self.assertTrue(all(row["passed"] for row in conformance.values()))
        specs = advanced_reducer_specs()
        cases = {
            "semantic_cache": WorkUnit(
                WorkUnitKind.PROMPT_REQUEST,
                "t",
                "app://q",
                requested_contract=Contract.SEMANTIC,
                policy_context={"allow_semantic_cache": True},
            ),
            "bounded_approximation": WorkUnit(
                WorkUnitKind.MEDIA_ASSET,
                "t",
                "media://asset",
                requested_contract=Contract.BOUNDED_APPROX,
                policy_context={"allow_bounded_approximation": True},
            ),
            "lakehouse_optimizer": WorkUnit(
                WorkUnitKind.TABLE_SNAPSHOT,
                "t",
                "lakehouse://table",
                requested_contract=Contract.EXACT_LOGICAL,
                policy_context={"allow_lakehouse_optimization": True},
            ),
            "training_reducer": WorkUnit(
                WorkUnitKind.TRAINING_DATASET,
                "t",
                "train://dataset",
                requested_contract=Contract.SEMANTIC,
                policy_context={"allow_training_reducer": True},
            ),
            "checkpoint_delta": WorkUnit(
                WorkUnitKind.MODEL_CHECKPOINT,
                "t",
                "checkpoint://model",
                requested_contract=Contract.EXACT_BYTES,
                policy_context={"allow_checkpoint_delta": True},
            ),
            "distillation": WorkUnit(
                WorkUnitKind.EVALUATION_JOB,
                "t",
                "eval://suite",
                requested_contract=Contract.SEMANTIC,
                policy_context={"allow_distillation": True},
            ),
        }
        for name, wu in cases.items():
            evidence = VerificationResult(True, f"{specs[name].required_verifier}@1", "accepted")
            decision = evaluate_reducer(wu, name, [evidence])
            self.assertTrue(decision.enabled, name)
            self.assertEqual(decision.action, specs[name].action)
            self.assertTrue(decision.benchmark_suite)
            self.assertTrue(decision.rollback)

    def test_built_in_adapters_have_contracts(self):
        adapters = built_in_adapters()
        for name in ["s3", "posix", "sql", "lakehouse", "stream", "otlp", "training", "vector", "edge", "cicd"]:
            self.assertIn(name, adapters)
            self.assertTrue(adapters[name].capabilities())
            self.assertTrue(adapter_conformance(name, adapters[name]).passed)
            if name not in {"s3", "posix"}:
                result = adapter_conformance(name, adapters[name])
                self.assertTrue(result.checks["mock_contract_methods"])
                self.assertTrue(result.checks["mock_external_free"])
        posix = adapter_conformance("posix", adapters["posix"])
        self.assertTrue(posix.checks["advertised_operations_callable"])
        self.assertTrue(posix.checks["posix_file_methods"])

    def test_live_adapter_readiness_and_aws_s3_signing(self):
        readiness = live_adapter_readiness("aws", env={})
        self.assertEqual(readiness["adapter_count"], 1)
        self.assertEqual(readiness["ready_count"], 0)
        self.assertIn("AWS_SECRET_ACCESS_KEY", readiness["adapters"][0]["missing_env"])
        config = AWSS3Config.from_env(
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCESS_KEY_ID": "AKIA_TEST",
                "AWS_SECRET_ACCESS_KEY": "secret",
                "URP_AWS_BUCKET": "urp-bucket",
                "URP_AWS_PREFIX": "tenant-a",
            }
        )
        adapter = AWSS3ObjectAdapter(config)
        signed = adapter._signed_headers("PUT", "https://urp-bucket.s3.us-east-1.amazonaws.com/tenant-a/object", b"payload", {})  # noqa: SLF001
        self.assertIn("AWS4-HMAC-SHA256", signed["authorization"])
        self.assertIn("x-amz-content-sha256", signed)
        self.assertEqual(adapter._key("object"), "tenant-a/object")  # noqa: SLF001

    def test_ai_gateway_conformance_contract(self):
        with tempfile.TemporaryDirectory() as td:
            result = ai_gateway_conformance(td)
            self.assertTrue(result.passed, result.to_dict())
            self.assertTrue(result.checks["chat_exact_cache_hit"])
            self.assertTrue(result.checks["cross_tenant_cache_blocked"])
            self.assertTrue(result.checks["prompt_redacted_from_manifests"])

    def test_metric_contract_names_exist(self):
        self.assertIn("urp_work_units_total", default_metric_names())
        self.assertIn("urp_ai_large_model_calls_avoided_total", default_metric_names())

    def test_log_template_extraction(self):
        extracted = extract_log_template("User 123 failed login from 10.0.0.1")
        self.assertEqual(extracted.template, "User <number> failed login from <ip>")
        grouped = group_log_templates(["User 123 failed login from 10.0.0.1", "User 456 failed login from 10.0.0.2"])
        self.assertEqual(grouped["User <number> failed login from <ip>"]["count"], 2)

    def test_local_authorizer(self):
        authorizer = LocalAuthorizer()
        self.assertTrue(authorizer.allowed(Principal("alice", "t", {"viewer"}), "manifest:read", "t"))
        self.assertFalse(authorizer.allowed(Principal("alice", "t", {"viewer"}), "work_unit:write", "t"))
        authenticator = APIKeyAuthenticator({"configured-secret": Principal("root", "*", {"admin"})})
        self.assertIn("admin", principal_from_api_key("configured-secret", "t", authenticator).roles)
        with self.assertRaises(Exception):
            principal_from_api_key("admin:root", "t", authenticator)

    def test_policy_override_audited(self):
        with tempfile.TemporaryDirectory() as td:
            wu = WorkUnit(WorkUnitKind.POLICY_OVERRIDE, "t", "policy://override")
            event = audit_policy_override(wu, Contract.SEMANTIC, "admin", "approved test override", default_ledger(td), approved=True)
            self.assertEqual(event.event_type, "policy.override.approved")
            self.assertEqual(default_ledger(td).read()[0].trace_id, wu.trace_id)

    def test_structured_error_model(self):
        err = verifier_failed("failed", work_unit_id="wu_test", details={"verifier": "sha256"})
        self.assertEqual(err.to_dict()["error"]["code"], "verifier_failed")
        self.assertFalse(err.to_dict()["error"]["retryable"])

    def test_release_signature_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("demo", encoding="utf-8")
            (root / "archive" / "source_packages").mkdir(parents=True)
            (root / "archive" / "source_packages" / "legacy.txt").write_text("legacy", encoding="utf-8")
            manifest = write_release_manifest(root)
            self.assertTrue((root / "PACKAGE_SHA256.json").exists())
            self.assertEqual(manifest["file_count"], 1)
            self.assertIn("content_digest", manifest)
            self.assertNotIn("attestation", manifest)
            self.assertEqual(manifest["scope"], "active_distribution")
            self.assertNotIn("archive/source_packages/legacy.txt", manifest["files"])
            signed = write_release_manifest(root, "SIGNED.json")
            self.assertNotIn("PACKAGE_SHA256.json", signed["files"])
            signing_key = base64.b64encode(b"s" * 32).decode("ascii")
            attested = build_release_manifest(root, signing_key=signing_key)
            self.assertEqual(attested["attestation"]["algorithm"], "ed25519")
            self.assertTrue(verify_release_manifest(attested, root)["passed"])

    def test_plugin_registry_and_package_conformance(self):
        with tempfile.TemporaryDirectory() as td:
            registry = PluginRegistry(td)
            source = (
                "def transform(value):\n"
                "    return value\n\n"
                "def urp_plugin_v1():\n"
                "    return {\n"
                "        'descriptor': {'api_version': 'urp.plugin.v1', 'name': 'local-transform', "
                "'version': '0.1.0', 'category': 'transforms'},\n"
                "        'operations': {'transform': transform},\n"
                "    }\n"
            )
            descriptor = _plugin_descriptor(hashlib.sha256(source.encode("utf-8")).hexdigest())
            registry.register(descriptor, actor="admin")
            self.assertEqual(registry.list()[0]["name"], "local-transform")
            package = Path(td) / "plugin_pkg"
            package.mkdir()
            (package / "plugin.yaml").write_text("name: local-transform\n", encoding="utf-8")
            (package / "README.md").write_text("# Local Transform\n", encoding="utf-8")
            (package / "security.md").write_text("# Security\n", encoding="utf-8")
            for folder in ["src", "tests", "conformance", "examples"]:
                (package / folder).mkdir()
            (package / "src" / "plugin.py").write_text(source, encoding="utf-8")
            (package / "plugin.json").write_text(json.dumps(descriptor), encoding="utf-8")
            self.assertTrue(plugin_package_conformance(package).passed)

    def test_repo_plugin_scaffolds_conform(self):
        root = Path(__file__).resolve().parents[2]
        packages = discover_plugin_packages(root / "plugins")
        categories = {path.parent.name for path in packages}
        self.assertTrue({"transforms", "classifiers", "verifiers", "adapters"}.issubset(categories))
        self.assertGreaterEqual(len(packages), 4)
        for package in packages:
            result = plugin_package_conformance(package)
            self.assertTrue(result.passed, result.to_dict())
            if package.name == "local-s3-adapter":
                descriptor = json.loads((package / "plugin.json").read_text(encoding="utf-8"))
                for capability in ["object.list", "object.delete", "metadata.headers", "object.tags"]:
                    self.assertIn(capability, descriptor["capabilities"])

    def test_sdk_builders_and_openapi_surface_exist(self):
        root = Path(__file__).resolve().parents[2]
        package = json.loads((root / "typescript/package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["main"], "dist/index.js")
        self.assertEqual(package["types"], "dist/index.d.ts")
        self.assertFalse(package.get("private", False))
        ts_src = (root / "typescript/src/index.ts").read_text(encoding="utf-8")
        ts_root = (root / "typescript/index.ts").read_text(encoding="utf-8")
        go_src = (root / "go/urp.go").read_text(encoding="utf-8")
        go_compat_src = (root / "go/urp/urp.go").read_text(encoding="utf-8")
        cargo_workspace = (root / "Cargo.toml").read_text(encoding="utf-8")
        rust_core = (root / "crates/urp-core/src/lib.rs").read_text(encoding="utf-8")
        rust_s3 = (root / "crates/urp-gateway-s3/src/lib.rs").read_text(encoding="utf-8")
        openapi = (root / "specs/openapi.yaml").read_text(encoding="utf-8")
        proto = (root / "specs/urp.proto").read_text(encoding="utf-8")
        for deployment_path in [
            "deployments/docker-compose/docker-compose.yaml",
            "deployments/kubernetes/urp-control-plane.yaml",
            "deployments/kubernetes/urp-multi-region.yaml",
            "deployments/operator/urp-operator.yaml",
            "deployments/terraform/aws/main.tf",
            "deployments/terraform/azure/main.tf",
            "deployments/terraform/gcp/main.tf",
            "deployments/on-prem/docker-compose.airgap.yaml",
            "deployments/on-prem/systemd/urp-control-plane.service",
            "deployments/edge/urp-edge-sidecar.yaml",
        ]:
            self.assertTrue((root / deployment_path).exists(), deployment_path)
        self.assertIn("class WorkUnitBuilder", ts_src)
        self.assertIn("traceId", ts_src)
        self.assertIn("async createWorkUnit", ts_src)
        self.assertIn("async listWorkUnits", ts_src)
        self.assertIn("async getWorkUnit", ts_src)
        self.assertIn("async planWorkUnit", ts_src)
        self.assertIn("async createPlan", ts_src)
        self.assertIn("async listPlans", ts_src)
        self.assertIn("async getPlan", ts_src)
        self.assertIn("async executeWorkUnit", ts_src)
        self.assertIn("async listManifests", ts_src)
        self.assertIn("async exportManifests", ts_src)
        self.assertIn("async exploreManifests", ts_src)
        self.assertIn("async rehydrateManifest", ts_src)
        self.assertIn("ledgerStreamUrl", ts_src)
        self.assertIn("async logsQuery", ts_src)
        self.assertIn("async savingsReport", ts_src)
        self.assertIn("async dashboardReport", ts_src)
        self.assertIn("async aiConformance", ts_src)
        self.assertIn("async productionReadiness", ts_src)
        self.assertIn("async platformProfiles", ts_src)
        self.assertIn("async platformReadiness", ts_src)
        self.assertIn("async platformMatrix", ts_src)
        self.assertIn("async reloadPolicyBundle", ts_src)
        self.assertIn("async exactCacheLookup", ts_src)
        self.assertIn("async storeCacheEntry", ts_src)
        self.assertIn("async s3PutObject", ts_src)
        self.assertIn("async s3ListObjects", ts_src)
        self.assertIn("async s3DeleteObject", ts_src)
        self.assertIn("async s3CreateMultipartUpload", ts_src)
        self.assertIn("async chatCompletions", ts_src)
        self.assertIn("async completions", ts_src)
        self.assertIn("async embeddings", ts_src)
        self.assertIn("async models", ts_src)
        self.assertIn("function fromApiWorkUnit", ts_src)
        self.assertIn('export * from "./src/index.js";', ts_root)
        self.assertIn("type WorkUnitBuilder struct", go_src)
        self.assertIn("func ByteObjectWorkUnit", go_src)
        self.assertIn("func (c *Client) CreateWorkUnit", go_src)
        self.assertIn("func (c *Client) ListWorkUnits", go_src)
        self.assertIn("func (c *Client) GetWorkUnit", go_src)
        self.assertIn("func (c *Client) PlanWorkUnit", go_src)
        self.assertIn("func (c *Client) CreatePlan", go_src)
        self.assertIn("func (c *Client) ListPlans", go_src)
        self.assertIn("func (c *Client) GetPlan", go_src)
        self.assertIn("func (c *Client) ExecuteWorkUnit", go_src)
        self.assertIn("func (c *Client) ListManifests", go_src)
        self.assertIn("func (c *Client) ExportManifests", go_src)
        self.assertIn("func (c *Client) ExploreManifests", go_src)
        self.assertIn("type ManifestRange struct", go_src)
        self.assertIn("func (c *Client) RehydrateManifest", go_src)
        self.assertIn("type LedgerQuery struct", go_src)
        self.assertIn("func (c *Client) LedgerStreamURL", go_src)
        self.assertIn("type LogQuery struct", go_src)
        self.assertIn("func (c *Client) LogsQuery", go_src)
        self.assertIn("type ReportQuery struct", go_src)
        self.assertIn("func (c *Client) SavingsReport", go_src)
        self.assertIn("func (c *Client) DashboardReport", go_src)
        self.assertIn("type ConformanceResult struct", go_src)
        self.assertIn("func (c *Client) AIConformance", go_src)
        self.assertIn("type ProductionReadinessResult struct", go_src)
        self.assertIn("func (c *Client) ProductionReadiness", go_src)
        self.assertIn("type PlatformProfile struct", go_src)
        self.assertIn("type PlatformReadinessResult struct", go_src)
        self.assertIn("type PlatformMatrix struct", go_src)
        self.assertIn("func (c *Client) PlatformProfiles", go_src)
        self.assertIn("func (c *Client) PlatformReadiness", go_src)
        self.assertIn("func (c *Client) PlatformMatrix", go_src)
        self.assertIn("type PolicyReloadResult struct", go_src)
        self.assertIn("func (c *Client) ReloadPolicyBundle", go_src)
        self.assertIn("type CacheLookupRequest struct", go_src)
        self.assertIn("func (c *Client) ExactCacheLookup", go_src)
        self.assertIn("func (c *Client) StoreCacheEntry", go_src)
        self.assertIn("type S3PutObjectRequest struct", go_src)
        self.assertIn("func (c *Client) S3PutObject", go_src)
        self.assertIn("func (c *Client) S3ListObjects", go_src)
        self.assertIn("func (c *Client) S3DeleteObject", go_src)
        self.assertIn("func (c *Client) S3CreateMultipartUpload", go_src)
        self.assertIn("func (c *Client) ChatCompletions", go_src)
        self.assertIn("func (c *Client) Completions", go_src)
        self.assertIn("func (c *Client) Embeddings", go_src)
        self.assertIn("func (c *Client) Models", go_src)
        self.assertIn('import root "github.com/thewisecrab/urp/go"', go_compat_src)
        self.assertIn("type WorkUnit = root.WorkUnit", go_compat_src)
        self.assertIn("type ManifestRange = root.ManifestRange", go_compat_src)
        self.assertIn("type ManifestExploreQuery = root.ManifestExploreQuery", go_compat_src)
        self.assertIn("type ReportQuery = root.ReportQuery", go_compat_src)
        self.assertIn("type LogQuery = root.LogQuery", go_compat_src)
        self.assertIn("type ConformanceResult = root.ConformanceResult", go_compat_src)
        self.assertIn("type ProductionReadinessResult = root.ProductionReadinessResult", go_compat_src)
        self.assertIn("type PlatformProfile = root.PlatformProfile", go_compat_src)
        self.assertIn("type PlatformReadinessResult = root.PlatformReadinessResult", go_compat_src)
        self.assertIn("type PlatformMatrix = root.PlatformMatrix", go_compat_src)
        self.assertIn("type PolicyReloadResult = root.PolicyReloadResult", go_compat_src)
        self.assertIn("type CacheLookupRequest = root.CacheLookupRequest", go_compat_src)
        self.assertIn("type S3PutObjectRequest = root.S3PutObjectRequest", go_compat_src)
        self.assertIn("var NewClient = root.NewClient", go_compat_src)
        self.assertIn('"crates/urp-core"', cargo_workspace)
        self.assertIn('"crates/urp-chunker"', cargo_workspace)
        self.assertIn('"crates/urp-gateway-s3"', cargo_workspace)
        self.assertIn("pub enum Contract", rust_core)
        self.assertIn("pub struct WorkUnit", rust_core)
        self.assertIn("pub struct PutObjectRequest", rust_s3)
        self.assertIn("into_work_unit", rust_s3)
        self.assertIn("pub struct ListObjectsRequest", rust_s3)
        self.assertIn("pub struct DeleteObjectRequest", rust_s3)
        for path in [
            "/v1/work-units",
            "/v1/work-units/plan",
            "/v1/work-units/execute",
            "/v1/plans",
            "/v1/plans/{id}",
            "/v1/work-units/{id}",
            "/v1/work-units/{id}/plan",
            "/v1/work-units/{id}/execute",
            "/v1/manifests",
            "/v1/manifests/explore",
            "/v1/manifests/{id}",
            "/v1/manifests/{id}/rehydrate",
            "/v1/manifests/export",
            "/v1/ledger/query",
            "/v1/ledger/stream",
            "/v1/logs/query",
            "/v1/reports/savings",
            "/v1/reports/dashboard",
            "/v1/conformance/ai",
            "/v1/policies/evaluate",
            "/v1/policies/validate",
            "/v1/policies/bundles",
            "/v1/policies/bundles/{name}/rollback",
            "/v1/policies/bundles/{name}/reload",
            "/v1/plugins",
            "/v1/plugins/register",
            "/v1/kms/keys",
            "/v1/admin/backup",
            "/v1/admin/restore",
            "/v1/admin/readiness",
            "/v1/platforms",
            "/v1/platforms/readiness",
            "/v1/platforms/matrix",
            "/v1/cache/exact/lookup",
            "/v1/cache/store",
            "/v1/cache/semantic/lookup",
            "/v1/models",
            "/v1/scheduler/submit",
            "/v1/scheduler/jobs",
            "/v1/s3/objects",
            "/v1/s3/objects/head",
            "/v1/s3/objects/get",
            "/v1/s3/objects/range",
            "/v1/s3/objects/list",
            "/v1/s3/objects/delete",
            "/v1/s3/multipart/create",
            "/v1/s3/multipart/part",
            "/v1/s3/multipart/complete",
            "/v1/s3/multipart/abort",
            "/v1/chat/completions",
            "/v1/completions",
            "/v1/embeddings",
        ]:
            self.assertIn(path, openapi)
        for service in [
            "WorkUnitService",
            "PlanService",
            "ManifestService",
            "PolicyService",
            "LedgerService",
            "CacheService",
            "AIService",
            "PluginService",
            "ObjectGatewayService",
            "SchedulerService",
            "AdminService",
            "PlatformService",
            "ObservabilityService",
        ]:
            self.assertIn(f"service {service}", proto)
        for rpc in [
            "CreateWorkUnit",
            "ListWorkUnits",
            "GetWorkUnit",
            "PlanWorkUnit",
            "ExecuteWorkUnit",
            "CreatePlan",
            "ListPlans",
            "GetPlan",
            "ListManifests",
            "GetManifest",
            "RehydrateManifest",
            "ExportManifests",
            "ExploreManifests",
            "EvaluatePolicy",
            "ValidatePolicy",
            "ListPolicyBundles",
            "PublishPolicyBundle",
            "RollbackPolicyBundle",
            "ReloadPolicyBundle",
            "QueryLedger",
            "StreamLedger",
            "LookupExactCache",
            "LookupSemanticCache",
            "StoreCacheEntry",
            "ChatCompletions",
            "Completions",
            "Embeddings",
            "ListModels",
            "RunAIConformance",
            "ListPlugins",
            "RegisterPlugin",
            "RunAdapterConformance",
            "PutObject",
            "RangeRead",
            "ListObjects",
            "DeleteObject",
            "SubmitJob",
            "BackupState",
            "CheckAuthorization",
            "GetProductionReadiness",
            "ListPlatformProfiles",
            "GetPlatformReadiness",
            "GetPlatformMatrix",
            "GetSavingsReport",
            "GetDashboardReport",
            "QueryTraces",
            "QueryLogs",
        ]:
            self.assertIn(f"rpc {rpc}", proto)
        for message in [
            "WorkUnit",
            "Plan",
            "Manifest",
            "LedgerEvent",
            "StructuredLogEntry",
            "ManifestExplorerReport",
            "PolicyDecision",
            "VerificationResult",
            "CacheLookupRequest",
            "OpenAIRequest",
            "PluginDescriptor",
            "ConformanceResult",
            "ProductionReadinessResult",
            "PlatformProfile",
            "PlatformReadinessResult",
            "PlatformMatrix",
            "PolicyReloadResult",
            "DashboardReport",
            "ListObjectsRequest",
            "DeleteObjectRequest",
            "ObjectList",
            "DeleteObjectResult",
            "SchedulerDecision",
        ]:
            self.assertIn(f"message {message}", proto)

    def test_clean_ci_installs_declared_runtime_dependencies(self):
        root = Path(__file__).resolve().parents[2]
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        ci = (root / ".github/workflows/ci.yaml").read_text(encoding="utf-8")
        license_text = (root / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("PyYAML", pyproject)
        self.assertIn('python3 -m pip install -e ".[dev]"', ci)
        self.assertIn("npm ci", ci)
        self.assertIn("working-directory: typescript", ci)
        self.assertIn("npm pack --dry-run", ci)
        self.assertIn("go test -race ./...", ci)
        self.assertIn("(except as stated in this section) patent license", license_text)
        self.assertIn("APPENDIX: How to apply the Apache License to your work.", license_text)

    def test_arxiv_publication_metadata_is_complete_and_ascii(self):
        root = Path(__file__).resolve().parents[2]
        author = "Siddharth Nilesh Patel"
        white_paper = (root / "docs/WHITE_PAPER.md").read_text(encoding="utf-8")
        citation = (root / "CITATION.cff").read_text(encoding="utf-8")
        renderer = (root / "scripts/render_whitepaper.py").read_text(encoding="utf-8")
        bundle = (root / "paper/arxiv/README.md").read_text(encoding="utf-8")
        for artifact in (white_paper, renderer, bundle):
            self.assertIn(author, artifact)
        self.assertIn('family-names: "Patel"', citation)
        self.assertIn('given-names: "Siddharth Nilesh"', citation)
        abstract = bundle.split("## Abstract\n\n", 1)[1].split("\n\n## Upload policy", 1)[0]
        abstract.encode("ascii")
        self.assertLessEqual(len(" ".join(abstract.split())), 1920)
        self.assertIn("cs.DC", bundle)
        self.assertIn("CC BY 4.0", bundle)

    def test_api_specs_parse_and_have_typed_operations(self):
        result = validate_api_specs(Path(__file__).resolve().parents[2])
        self.assertTrue(result.passed, result.to_dict())
        self.assertGreaterEqual(result.details["openapi_operation_count"], 20)
        self.assertIn("WorkUnitService", result.details["proto_services"])
        self.assertIn("PlatformService", result.details["proto_services"])


if __name__ == "__main__":
    unittest.main()
