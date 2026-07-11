from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml


@dataclass(frozen=True)
class DeploymentValidationResult:
    passed: bool
    checks: Dict[str, bool]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"passed": self.passed, "checks": self.checks, "details": self.details}


def validate_deployment_artifacts(repo_root: str | Path) -> DeploymentValidationResult:
    root = Path(repo_root)
    kubernetes_paths = [
        root / "deployments/kubernetes/urp-control-plane.yaml",
        root / "deployments/kubernetes/urp-multi-region.yaml",
        root / "deployments/operator/urp-operator.yaml",
        root / "deployments/edge/urp-edge-sidecar.yaml",
    ]
    terraform_paths = [
        root / "deployments/terraform/aws/main.tf",
        root / "deployments/terraform/azure/main.tf",
        root / "deployments/terraform/gcp/main.tf",
    ]
    compose = root / "deployments/docker-compose/docker-compose.yaml"
    dockerfile = root / "deployments/docker/Dockerfile"
    helm_chart = root / "deployments/helm/urp/Chart.yaml"
    helm_values = root / "deployments/helm/urp/values.yaml"
    helm_deployment = root / "deployments/helm/urp/templates/deployment.yaml"
    parsed_kubernetes = {str(path.relative_to(root)): _load_yaml_docs(path) for path in kubernetes_paths if path.exists()}
    terraform_texts = {str(path.relative_to(root)): path.read_text(encoding="utf-8") for path in terraform_paths if path.exists()}
    compose_text = compose.read_text(encoding="utf-8") if compose.exists() else ""
    compose_document = yaml.safe_load(compose_text) if compose_text else {}
    workload_docs = [
        doc
        for path, docs in parsed_kubernetes.items()
        if path
        in {
            "deployments/kubernetes/urp-control-plane.yaml",
            "deployments/kubernetes/urp-multi-region.yaml",
            "deployments/operator/urp-operator.yaml",
            "deployments/edge/urp-edge-sidecar.yaml",
        }
        for doc in docs
        if doc.get("kind") in {"Deployment", "DaemonSet"}
    ]
    checks = {
        "deployment_files_present": all(
            path.exists() for path in [*kubernetes_paths, *terraform_paths, compose, dockerfile, helm_chart, helm_values, helm_deployment]
        ),
        "kubernetes_yaml_parseable": all(_has_api_shape(doc) for docs in parsed_kubernetes.values() for doc in docs),
        "kubernetes_workloads_have_health_probes": all(_health_probes_are_distinct(workload) for workload in workload_docs),
        "kubernetes_workloads_have_resource_bounds": all(_containers_have(workload, "resources") for workload in workload_docs),
        "kubernetes_workloads_hardened": all(_workload_hardened(workload) for workload in workload_docs),
        "kubernetes_images_version_pinned": all(_images_version_pinned(workload) for workload in workload_docs),
        "terraform_required_providers_declared": all("required_providers" in text and "provider " in text and "backend " in text for text in terraform_texts.values()),
        "terraform_object_and_kms_backends_declared": (
            "aws_s3_bucket_versioning" in terraform_texts.get("deployments/terraform/aws/main.tf", "")
            and "aws_s3_bucket_server_side_encryption_configuration" in terraform_texts.get("deployments/terraform/aws/main.tf", "")
            and "azurerm_key_vault" in terraform_texts.get("deployments/terraform/azure/main.tf", "")
            and "google_kms_crypto_key" in terraform_texts.get("deployments/terraform/gcp/main.tf", "")
        ),
        "terraform_azure_versioning_valid_shape": "blob_properties" in terraform_texts.get("deployments/terraform/azure/main.tf", "") and "\n  versioning_enabled" not in terraform_texts.get("deployments/terraform/azure/main.tf", ""),
        "docker_image_build_declared": "FROM python:" in dockerfile.read_text(encoding="utf-8") if dockerfile.exists() else False,
        "docker_compose_services_complete": _compose_services_complete(compose_document),
        "docker_compose_stateful_backends_declared": "postgres:" in compose_text and "URP_MANIFEST_STORE" in compose_text and "URP_LEDGER_STORE" in compose_text,
        "docker_compose_auth_and_secret_indirection": "URP_LOCAL_API_KEY" in compose_text and ":?Set " in compose_text and "POSTGRES_PASSWORD: urp" not in compose_text,
        "helm_chart_hardened_defaults": _helm_chart_hardened(helm_chart, helm_values, helm_deployment),
        "operator_crd_schema_declared": any(
            doc.get("kind") == "CustomResourceDefinition" and "openAPIV3Schema" in str(doc)
            for docs in parsed_kubernetes.values()
            for doc in docs
        ),
        "operator_controller_implemented": (root / "python/urp/operator.py").exists() and "python\", \"-m\", \"urp.operator" in (root / "deployments/operator/urp-operator.yaml").read_text(encoding="utf-8"),
    }
    details = {
        "kubernetes_files": sorted(parsed_kubernetes),
        "terraform_files": sorted(terraform_texts),
        "workload_count": len(workload_docs),
        "helm_chart": str(helm_chart.relative_to(root)) if helm_chart.exists() else None,
    }
    return DeploymentValidationResult(all(checks.values()), checks, details)


def _load_yaml_docs(path: Path) -> list[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        docs = [doc for doc in yaml.safe_load_all(fh) if doc]
    return [doc if isinstance(doc, dict) else {} for doc in docs]


def _has_api_shape(doc: Dict[str, Any]) -> bool:
    return bool(doc.get("apiVersion")) and bool(doc.get("kind")) and isinstance(doc.get("metadata"), dict) and bool(doc["metadata"].get("name"))


def _containers_have(workload: Dict[str, Any], *keys: str) -> bool:
    containers = _containers(workload)
    return bool(containers) and all(all(key in container for key in keys) for container in containers)


def _containers(workload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    spec = workload.get("spec", {})
    template = spec.get("template", {}) if isinstance(spec, dict) else {}
    pod_spec = template.get("spec", {}) if isinstance(template, dict) else {}
    containers = pod_spec.get("containers", []) if isinstance(pod_spec, dict) else []
    return [container for container in containers if isinstance(container, dict)]


def _health_probes_are_distinct(workload: Dict[str, Any]) -> bool:
    containers = list(_containers(workload))
    if not containers:
        return False
    for container in containers:
        readiness = container.get("readinessProbe", {}).get("httpGet", {}).get("path")
        liveness = container.get("livenessProbe", {}).get("httpGet", {}).get("path")
        if readiness != "/readyz" or liveness != "/healthz":
            return False
    return True


def _workload_hardened(workload: Dict[str, Any]) -> bool:
    template = workload.get("spec", {}).get("template", {})
    pod_spec = template.get("spec", {}) if isinstance(template, dict) else {}
    pod_security = pod_spec.get("securityContext", {}) if isinstance(pod_spec, dict) else {}
    if pod_security.get("runAsNonRoot") is not True:
        return False
    for container in _containers(workload):
        security = container.get("securityContext", {})
        if security.get("allowPrivilegeEscalation") is not False or security.get("readOnlyRootFilesystem") is not True:
            return False
        if "ALL" not in security.get("capabilities", {}).get("drop", []):
            return False
    return True


def _images_version_pinned(workload: Dict[str, Any]) -> bool:
    images = [str(container.get("image", "")) for container in _containers(workload)]
    return bool(images) and all(image and not image.endswith(":latest") and not image.endswith(":dev") for image in images)


def _compose_services_complete(document: Dict[str, Any]) -> bool:
    services = document.get("services", {}) if isinstance(document, dict) else {}
    required = {"control-plane", "gateway-ai", "gateway-s3", "worker", "scheduler", "postgres"}
    return isinstance(services, dict) and required <= set(services)


def _helm_chart_hardened(chart: Path, values: Path, deployment: Path) -> bool:
    if not all(path.is_file() for path in (chart, values, deployment)):
        return False
    chart_doc = yaml.safe_load(chart.read_text(encoding="utf-8"))
    values_doc = yaml.safe_load(values.read_text(encoding="utf-8"))
    template = deployment.read_text(encoding="utf-8")
    return bool(
        isinstance(chart_doc, dict)
        and chart_doc.get("apiVersion") == "v2"
        and isinstance(values_doc, dict)
        and values_doc.get("mode") == "observe"
        and values_doc.get("secrets", {}).get("create") is False
        and values_doc.get("securityContext", {}).get("readOnlyRootFilesystem") is True
        and "startupProbe:" in template
        and "readinessProbe:" in template
        and "livenessProbe:" in template
        and "resources:" in template
    )
