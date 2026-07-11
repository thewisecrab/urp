from __future__ import annotations

import json
import os
import ssl
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib import error, parse, request


@dataclass
class OperatorStatus:
    ready: bool = False
    last_reconcile_at: float | None = None
    last_error: str = ""
    reconciled_resources: int = 0


class KubernetesClient:
    def __init__(self) -> None:
        host = os.environ.get("KUBERNETES_SERVICE_HOST")
        port = os.environ.get("KUBERNETES_SERVICE_PORT_HTTPS", "443")
        if not host:
            raise RuntimeError("KUBERNETES_SERVICE_HOST is required")
        self.base_url = f"https://{host}:{port}"
        token_path = Path(os.environ.get("URP_KUBERNETES_TOKEN_FILE", "/var/run/secrets/kubernetes.io/serviceaccount/token"))
        ca_path = Path(os.environ.get("URP_KUBERNETES_CA_FILE", "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"))
        self.token = token_path.read_text(encoding="utf-8").strip()
        self.context = ssl.create_default_context(cafile=str(ca_path))

    def get(self, path: str) -> Dict[str, Any]:
        return self._request("GET", path)

    def apply(self, path: str, value: Dict[str, Any]) -> Dict[str, Any]:
        query = parse.urlencode({"fieldManager": "urp-operator", "force": "true"})
        return self._request("PATCH", f"{path}?{query}", value, "application/apply-patch+yaml")

    def patch_status(self, path: str, value: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PATCH", path, value, "application/merge-patch+json")

    def _request(self, method: str, path: str, value: Dict[str, Any] | None = None, content_type: str = "application/json") -> Dict[str, Any]:
        data = json.dumps(value).encode("utf-8") if value is not None else None
        http_request = request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"authorization": f"Bearer {self.token}", "accept": "application/json", "content-type": content_type},
        )
        try:
            with request.urlopen(http_request, timeout=30, context=self.context) as response:  # noqa: S310 - Kubernetes service endpoint
                body = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Kubernetes API returned HTTP {exc.code}: {detail}") from exc
        return json.loads(body) if body else {}


class URPOperator:
    def __init__(self, client: KubernetesClient, namespace: str, status: OperatorStatus) -> None:
        self.client = client
        self.namespace = namespace
        self.status = status
        self.resource_path = f"/apis/urp.dev/v1alpha1/namespaces/{namespace}/urpcontrolplanes"

    def run(self) -> None:
        interval = max(5, int(os.environ.get("URP_OPERATOR_INTERVAL_SECONDS", "15")))
        while True:
            try:
                document = self.client.get(self.resource_path)
                resources = document.get("items", [])
                for resource in resources:
                    self.reconcile(resource)
                self.status.ready = True
                self.status.last_error = ""
                self.status.last_reconcile_at = time.time()
                self.status.reconciled_resources = len(resources)
            except Exception as exc:  # pragma: no cover - requires live cluster
                self.status.ready = False
                self.status.last_error = str(exc)[:2048]
            time.sleep(interval)

    def reconcile(self, resource: Dict[str, Any]) -> None:
        metadata = resource.get("metadata", {})
        spec = resource.get("spec", {})
        name = str(metadata["name"])
        replicas = int(spec.get("replicas", 1))
        if replicas < 1 or replicas > 20:
            raise ValueError("spec.replicas must be between 1 and 20")
        mode = str(spec.get("mode", "observe"))
        if mode not in {"observe", "shadow", "enforce"}:
            raise ValueError("spec.mode must be observe, shadow, or enforce")
        image = str(spec.get("image", "ghcr.io/thewisecrab/urp:0.1.0"))
        labels = {"app.kubernetes.io/name": "urp", "app.kubernetes.io/instance": name, "app.kubernetes.io/managed-by": "urp-operator"}
        owner = {
            "apiVersion": "urp.dev/v1alpha1",
            "kind": "URPControlPlane",
            "name": name,
            "uid": metadata["uid"],
            "controller": True,
            "blockOwnerDeletion": True,
        }
        deployment = _deployment(name, labels, owner, replicas, mode, image, spec)
        service = _service(name, labels, owner)
        self.client.apply(f"/apis/apps/v1/namespaces/{self.namespace}/deployments/{name}", deployment)
        self.client.apply(f"/api/v1/namespaces/{self.namespace}/services/{name}", service)
        generation = int(metadata.get("generation", 0))
        status_path = f"{self.resource_path}/{name}/status"
        self.client.patch_status(
            status_path,
            {
                "status": {
                    "observedGeneration": generation,
                    "readyReplicas": 0,
                    "conditions": [
                        {
                            "type": "Reconciled",
                            "status": "True",
                            "reason": "ResourcesApplied",
                            "message": "Deployment and Service applied",
                            "lastTransitionTime": _rfc3339_now(),
                        }
                    ],
                }
            },
        )


def run_operator() -> None:
    namespace_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
    namespace = os.environ.get("POD_NAMESPACE") or namespace_path.read_text(encoding="utf-8").strip()
    status = OperatorStatus()
    server = _health_server(status, os.environ.get("URP_OPERATOR_LISTEN", "0.0.0.0:8080"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    URPOperator(KubernetesClient(), namespace, status).run()


def _deployment(
    name: str,
    labels: Dict[str, str],
    owner: Dict[str, Any],
    replicas: int,
    mode: str,
    image: str,
    spec: Dict[str, Any],
) -> Dict[str, Any]:
    secret = str(spec.get("runtimeSecret", "urp-runtime"))
    state_claim = str(spec.get("stateClaim", "urp-state"))
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name, "labels": labels, "ownerReferences": [owner]},
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": labels},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "automountServiceAccountToken": False,
                    "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001, "fsGroup": 10001, "seccompProfile": {"type": "RuntimeDefault"}},
                    "containers": [
                        {
                            "name": "control-plane",
                            "image": image,
                            "args": ["service", "run", "--name", "control-plane", "--listen", "0.0.0.0:8080"],
                            "ports": [{"name": "http", "containerPort": 8080}],
                            "env": [
                                {"name": "URP_MODE", "value": mode},
                                {"name": "URP_LOCAL_API_KEY", "valueFrom": {"secretKeyRef": {"name": secret, "key": "api-key"}}},
                                {"name": "URP_MANIFEST_STORE", "valueFrom": {"secretKeyRef": {"name": secret, "key": "postgres-dsn"}}},
                                {"name": "URP_LEDGER_STORE", "valueFrom": {"secretKeyRef": {"name": secret, "key": "postgres-dsn"}}},
                            ],
                            "volumeMounts": [{"name": "state", "mountPath": "/var/lib/urp/.urp"}],
                            "readinessProbe": {"httpGet": {"path": "/readyz", "port": "http"}, "periodSeconds": 10},
                            "livenessProbe": {"httpGet": {"path": "/healthz", "port": "http"}, "periodSeconds": 20},
                            "resources": {"requests": {"cpu": "250m", "memory": "256Mi"}, "limits": {"cpu": "1", "memory": "1Gi"}},
                            "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}},
                        }
                    ],
                    "volumes": [{"name": "state", "persistentVolumeClaim": {"claimName": state_claim}}],
                },
            },
        },
    }


def _service(name: str, labels: Dict[str, str], owner: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name, "labels": labels, "ownerReferences": [owner]},
        "spec": {"selector": labels, "ports": [{"name": "http", "port": 8080, "targetPort": "http"}]},
    }


def _health_server(status: OperatorStatus, listen: str) -> ThreadingHTTPServer:
    host, port_text = listen.rsplit(":", 1)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path not in {"/healthz", "/readyz"}:
                self.send_response(404)
                self.end_headers()
                return
            ready = self.path == "/healthz" or status.ready
            body = json.dumps(
                {
                    "ok": ready,
                    "last_reconcile_at": status.last_reconcile_at,
                    "last_error": status.last_error,
                    "reconciled_resources": status.reconciled_resources,
                }
            ).encode("utf-8")
            self.send_response(200 if ready else 503)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host, int(port_text)), Handler)


def _rfc3339_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    run_operator()
