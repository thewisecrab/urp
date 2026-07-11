from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping

from .live_adapters import live_adapter_readiness


@dataclass(frozen=True)
class PlatformProfile:
    name: str
    display_name: str
    category: str
    deployment_targets: list[str]
    storage_backends: list[str]
    compute_backends: list[str]
    ai_providers: list[str]
    required_capabilities: list[str]
    required_artifacts: list[str]
    live_credential_env: list[str] = field(default_factory=list)
    optional_env: list[str] = field(default_factory=list)
    config_keys: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "category": self.category,
            "deployment_targets": self.deployment_targets,
            "storage_backends": self.storage_backends,
            "compute_backends": self.compute_backends,
            "ai_providers": self.ai_providers,
            "required_capabilities": self.required_capabilities,
            "required_artifacts": self.required_artifacts,
            "live_credential_env": self.live_credential_env,
            "optional_env": self.optional_env,
            "config_keys": self.config_keys,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class PlatformReadinessResult:
    target: str
    contract_ready: bool
    live_ready: bool
    passed: bool
    checks: Dict[str, bool]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "contract_ready": self.contract_ready,
            "live_ready": self.live_ready,
            "passed": self.passed,
            "checks": self.checks,
            "details": self.details,
        }


def built_in_platform_profiles() -> Dict[str, PlatformProfile]:
    base_capabilities = [
        "work_unit_lifecycle",
        "policy_evaluation",
        "manifest_store",
        "ledger",
        "rehydration",
        "observability",
        "adapter_conformance",
    ]
    return {
        "local": PlatformProfile(
            name="local",
            display_name="Local developer and single-node runtime",
            category="runtime",
            deployment_targets=["macOS", "Linux", "Windows via Python runtime"],
            storage_backends=["file", "sqlite", "local chunks"],
            compute_backends=["local process", "mock providers"],
            ai_providers=["mock", "OpenAI-compatible mock"],
            required_capabilities=[*base_capabilities, "exact_object_execution", "local_ai_gateway"],
            required_artifacts=["python/urp", "README.md", "specs/openapi.yaml"],
            optional_env=["URP_STATE_DIR"],
            config_keys=["state_dir", "manifest_backend"],
            notes=["No external credentials required."],
        ),
        "kubernetes": PlatformProfile(
            name="kubernetes",
            display_name="Kubernetes and operator-managed clusters",
            category="orchestration",
            deployment_targets=["EKS", "AKS", "GKE", "OpenShift", "vanilla Kubernetes"],
            storage_backends=["Postgres", "object store", "persistent volume"],
            compute_backends=["Deployments", "Jobs", "CronJobs", "operator"],
            ai_providers=["OpenAI-compatible gateways", "private model services"],
            required_capabilities=[*base_capabilities, "health_checks", "horizontal_scaling", "operator_manifest"],
            required_artifacts=[
                "deployments/kubernetes/urp-control-plane.yaml",
                "deployments/kubernetes/urp-multi-region.yaml",
                "deployments/operator/urp-operator.yaml",
                "deployments/helm/urp/Chart.yaml",
            ],
            live_credential_env=["KUBECONFIG"],
            optional_env=["URP_K8S_NAMESPACE", "URP_K8S_CONTEXT"],
            config_keys=["namespace", "replicas", "ingress", "storage_class"],
            notes=["Live cluster operations require kubeconfig or workload identity."],
        ),
        "aws": PlatformProfile(
            name="aws",
            display_name="Amazon Web Services",
            category="cloud",
            deployment_targets=["EKS", "ECS", "EC2", "Lambda-compatible workers"],
            storage_backends=["S3", "RDS Postgres", "EBS/EFS"],
            compute_backends=["EKS", "ECS", "Batch"],
            ai_providers=["Bedrock", "SageMaker", "OpenAI-compatible gateways"],
            required_capabilities=[*base_capabilities, "versioned_object_backend", "managed_postgres", "kms_envelope"],
            required_artifacts=["deployments/terraform/aws/main.tf", "python/urp/live_adapters.py"],
            live_credential_env=["AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "URP_AWS_BUCKET"],
            optional_env=["AWS_PROFILE", "AWS_ROLE_ARN", "AWS_SESSION_TOKEN", "AWS_S3_ENDPOINT", "URP_AWS_KMS_KEY_ID"],
            config_keys=["region", "bucket", "postgres_dsn", "kms_key_id"],
            notes=["Use IAM role based credentials in production; static keys are only a generic readiness signal."],
        ),
        "azure": PlatformProfile(
            name="azure",
            display_name="Microsoft Azure",
            category="cloud",
            deployment_targets=["AKS", "Container Apps", "VM Scale Sets"],
            storage_backends=["Blob Storage", "Azure Database for PostgreSQL", "Managed Disk"],
            compute_backends=["AKS", "Container Apps", "Batch"],
            ai_providers=["Azure OpenAI", "OpenAI-compatible gateways"],
            required_capabilities=[*base_capabilities, "versioned_object_backend", "managed_postgres", "key_vault_envelope"],
            required_artifacts=["deployments/terraform/azure/main.tf", "python/urp/live_adapters.py"],
            live_credential_env=["AZURE_STORAGE_ACCOUNT", "AZURE_STORAGE_KEY", "URP_AZURE_CONTAINER"],
            optional_env=["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID", "URP_AZURE_KEY_VAULT"],
            config_keys=["tenant_id", "subscription_id", "resource_group", "storage_account", "postgres_dsn", "key_vault_key_id"],
            notes=["Live deployment should use workload identity or managed identity where available."],
        ),
        "gcp": PlatformProfile(
            name="gcp",
            display_name="Google Cloud Platform",
            category="cloud",
            deployment_targets=["GKE", "Cloud Run", "Compute Engine"],
            storage_backends=["Cloud Storage", "Cloud SQL Postgres", "Persistent Disk"],
            compute_backends=["GKE", "Cloud Run Jobs", "Batch"],
            ai_providers=["Vertex AI", "OpenAI-compatible gateways"],
            required_capabilities=[*base_capabilities, "versioned_object_backend", "managed_postgres", "cloud_kms_envelope"],
            required_artifacts=["deployments/terraform/gcp/main.tf", "python/urp/live_adapters.py"],
            live_credential_env=["GOOGLE_CLOUD_PROJECT", "URP_GCP_BUCKET"],
            optional_env=["GOOGLE_APPLICATION_CREDENTIALS", "URP_GCP_KMS_KEY"],
            config_keys=["project_id", "region", "bucket", "postgres_instance", "kms_key_id"],
            notes=["Live deployment should prefer Workload Identity Federation over long-lived keys."],
        ),
        "on_prem": PlatformProfile(
            name="on_prem",
            display_name="On-premises and air-gapped environments",
            category="private_infrastructure",
            deployment_targets=["bare metal", "VMware", "OpenShift", "air-gapped Kubernetes", "systemd"],
            storage_backends=["MinIO", "Ceph", "NAS", "local Postgres"],
            compute_backends=["systemd", "Kubernetes", "batch schedulers"],
            ai_providers=["local model servers", "OpenAI-compatible private gateways"],
            required_capabilities=[*base_capabilities, "airgap_bundle", "local_kms_hook", "backup_restore"],
            required_artifacts=["deployments/on-prem/docker-compose.airgap.yaml", "deployments/on-prem/systemd/urp-control-plane.service"],
            live_credential_env=["URP_ON_PREM_POSTGRES_DSN", "URP_ON_PREM_OBJECT_ENDPOINT"],
            optional_env=["URP_ON_PREM_CA_BUNDLE", "URP_ON_PREM_KMS_ENDPOINT"],
            config_keys=["object_endpoint", "postgres_dsn", "ca_bundle", "offline_policy_bundle"],
            notes=["Designed to work without public cloud connectivity."],
        ),
        "edge": PlatformProfile(
            name="edge",
            display_name="Edge, branch, and intermittently connected sites",
            category="edge",
            deployment_targets=["K3s", "MicroK8s", "single-node Linux", "IoT gateways"],
            storage_backends=["local chunks", "delayed ledger sync", "local exact cache"],
            compute_backends=["sidecar", "daemonset", "systemd"],
            ai_providers=["local models", "regional fallback gateways"],
            required_capabilities=[*base_capabilities, "offline_policy_cache", "delayed_ledger_sync", "small_footprint"],
            required_artifacts=["deployments/edge/urp-edge-sidecar.yaml"],
            live_credential_env=["URP_EDGE_SITE_ID"],
            optional_env=["URP_EDGE_SYNC_ENDPOINT", "URP_EDGE_POLICY_BUNDLE"],
            config_keys=["site_id", "sync_endpoint", "policy_cache_ttl_seconds", "max_cache_bytes"],
            notes=["Edge mode favors exact cache, local policy cache, and delayed sync."],
        ),
        "openai_compatible": PlatformProfile(
            name="openai_compatible",
            display_name="OpenAI-compatible model providers",
            category="provider",
            deployment_targets=["OpenAI", "Azure OpenAI", "self-hosted compatible gateways", "Bedrock-compatible proxy"],
            storage_backends=["compute manifests", "exact cache"],
            compute_backends=["chat completions", "text completions", "embeddings"],
            ai_providers=["OpenAI-compatible"],
            required_capabilities=[*base_capabilities, "chat_completions", "text_completions", "embeddings", "model_listing"],
            required_artifacts=["specs/openapi.yaml", "services/gateway-ai/README.md", "python/urp/live_adapters.py"],
            live_credential_env=["OPENAI_API_KEY"],
            optional_env=["OPENAI_BASE_URL", "AZURE_OPENAI_ENDPOINT", "URP_AI_PROVIDER"],
            config_keys=["base_url", "api_key_secret", "model_allowlist", "fallback_model"],
            notes=["The local gateway is compatibility-first; live providers are opt-in adapters."],
        ),
        "cicd": PlatformProfile(
            name="cicd",
            display_name="CI/CD and release pipelines",
            category="delivery",
            deployment_targets=["GitHub Actions", "GitLab CI", "Buildkite", "Jenkins"],
            storage_backends=["artifact store", "release manifest"],
            compute_backends=["test runners", "release signing"],
            ai_providers=["mock", "optional provider conformance"],
            required_capabilities=[*base_capabilities, "release_signature", "schema_validation", "test_matrix"],
            required_artifacts=[".github/workflows/ci.yaml", "PACKAGE_SHA256.json"],
            live_credential_env=["CI"],
            optional_env=["GITHUB_TOKEN", "BUILDKITE", "GITLAB_CI"],
            config_keys=["python_version", "node_version", "go_version", "cargo_optional"],
            notes=["CI readiness validates the portable test and release-signing path."],
        ),
    }


def platform_matrix(repo_root: str | Path | None = None, env: Mapping[str, str] | None = None) -> Dict[str, Any]:
    root = _root(repo_root)
    rows = [platform_readiness(name, root, env).to_dict() for name in built_in_platform_profiles()]
    return {
        "platform_count": len(rows),
        "contract_ready_count": sum(1 for row in rows if row["contract_ready"]),
        "live_ready_count": sum(1 for row in rows if row["live_ready"]),
        "targets": rows,
    }


def platform_readiness(
    target: str = "all",
    repo_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    require_live: bool = False,
) -> PlatformReadinessResult | list[PlatformReadinessResult]:
    profiles = built_in_platform_profiles()
    root = _root(repo_root)
    current_env = dict(os.environ if env is None else env)
    if target == "all":
        return [platform_readiness(name, root, current_env, require_live) for name in profiles]
    if target not in profiles:
        raise KeyError(target)
    profile = profiles[target]
    artifact_checks = {f"artifact:{artifact}": (root / artifact).exists() for artifact in profile.required_artifacts}
    capability_checks = {
        f"capability:{capability}": _capability_ready(capability, profile.name, root)
        for capability in profile.required_capabilities
    }
    env_checks = {f"env:{name}": bool(current_env.get(name)) for name in profile.live_credential_env}
    contract_ready = all(artifact_checks.values()) and all(capability_checks.values())
    adapter_readiness = live_adapter_readiness(profile.name, current_env)
    adapter_ready = adapter_readiness["adapter_count"] == 0 or adapter_readiness["ready_count"] == adapter_readiness["adapter_count"]
    live_ready = contract_ready and all(env_checks.values()) and adapter_ready
    passed = live_ready if require_live else contract_ready
    checks = {**artifact_checks, **capability_checks, **env_checks}
    details = {
        "profile": profile.to_dict(),
        "mode": "live" if require_live else "contract",
        "missing_artifacts": [artifact for artifact in profile.required_artifacts if not (root / artifact).exists()],
        "missing_live_env": [name for name in profile.live_credential_env if not current_env.get(name)],
        "live_adapters": adapter_readiness,
        "credential_policy": "Live integrations require environment-specific credentials; contract readiness does not require them.",
        "repo_root": str(root),
    }
    return PlatformReadinessResult(profile.name, contract_ready, live_ready, passed, checks, details)


def _root(repo_root: str | Path | None) -> Path:
    configured = os.environ.get("URP_REPO_ROOT")
    return Path(repo_root or configured) if (repo_root or configured) else Path(__file__).resolve().parents[2]


def _capability_ready(capability: str, target: str, root: Path) -> bool:
    evidence: Dict[str, list[tuple[str, str]]] = {
        "work_unit_lifecycle": [("python/urp/work_unit_store.py", "class FileWorkUnitStore"), ("python/urp/executor.py", "def execute_work_unit")],
        "policy_evaluation": [("python/urp/policy.py", "def evaluate_policy")],
        "manifest_store": [("python/urp/manifest_store.py", "class FileManifestStore")],
        "ledger": [("python/urp/ledger.py", "class JSONLLedger")],
        "rehydration": [("python/urp/executor.py", "def rehydrate_manifest")],
        "observability": [("python/urp/metrics.py", "prometheus"), ("python/urp/structured_logs.py", "class JSONLLogStore")],
        "adapter_conformance": [("python/urp/plugins.py", "def adapter_conformance")],
        "exact_object_execution": [("python/urp/executor.py", "def execute_exact_object")],
        "local_ai_gateway": [("python/urp/ai_gateway.py", "def handle_chat_completion")],
        "health_checks": [("python/urp/health.py", "def dependency_readiness"), ("specs/openapi.yaml", "/readyz")],
        "horizontal_scaling": [("deployments/kubernetes/urp-control-plane.yaml", "replicas: 2"), ("python/urp/postgres.py", "class PostgresLedger")],
        "operator_manifest": [("python/urp/operator.py", "class URPOperator"), ("deployments/operator/urp-operator.yaml", "kind: CustomResourceDefinition")],
        "versioned_object_backend": [(f"deployments/terraform/{target}/main.tf", "versioning")],
        "managed_postgres": [("python/urp/postgres.py", "class PostgresManifestStore"), ("python/urp/postgres.py", "class PostgresLedger")],
        "kms_envelope": [("python/urp/kms.py", "AESGCM")],
        "key_vault_envelope": [("deployments/terraform/azure/main.tf", "azurerm_key_vault_key")],
        "cloud_kms_envelope": [("deployments/terraform/gcp/main.tf", "google_kms_crypto_key")],
        "airgap_bundle": [("deployments/on-prem/docker-compose.airgap.yaml", "URP_AIRGAP_MODE")],
        "local_kms_hook": [("python/urp/kms.py", "class LocalKMS")],
        "backup_restore": [("python/urp/disaster_recovery.py", "def import_state")],
        "offline_policy_cache": [("python/urp/policy_store.py", "class PolicyBundleStore")],
        "delayed_ledger_sync": [("python/urp/edge_sync.py", "class DelayedLedgerSync")],
        "small_footprint": [("deployments/edge/urp-edge-sidecar.yaml", "kind: DaemonSet")],
        "chat_completions": [("python/urp/ai_gateway.py", "def handle_chat_completion")],
        "text_completions": [("python/urp/ai_gateway.py", "def handle_completion")],
        "embeddings": [("python/urp/ai_gateway.py", "def handle_embeddings")],
        "model_listing": [("python/urp/ai_gateway.py", "def list_models")],
        "release_signature": [("python/urp/release.py", "Ed25519PrivateKey")],
        "schema_validation": [("python/urp/schema_validation.py", "Draft202012Validator")],
        "test_matrix": [(".github/workflows/ci.yaml", "strategy:")],
    }
    requirements = evidence.get(capability)
    if not requirements:
        return False
    for relative, token in requirements:
        path = root / relative
        if not path.is_file():
            return False
        try:
            if token not in path.read_text(encoding="utf-8"):
                return False
        except UnicodeDecodeError:
            return False
    return True
