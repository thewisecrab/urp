# Deployment Quickstart

URP supports local processes, Docker Compose, Kubernetes/Helm, and reference cloud
infrastructure. Start in `observe` mode and promote only after reviewing manifests,
verifier outcomes, latency, and cost telemetry.

## Local process

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[api,production]"
export URP_LOCAL_API_KEY="$(openssl rand -hex 32)"
.venv/bin/urp --state-dir .urp service run \
  --name control-plane \
  --listen 127.0.0.1:8080
```

Probe it:

```bash
curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8080/readyz
curl -H "Authorization: Bearer $URP_LOCAL_API_KEY" \
  http://127.0.0.1:8080/v1/manifests
```

## Docker Compose

```bash
cp .env.example .env
# Replace every CHANGE_ME value.
docker compose -f deployments/docker-compose/docker-compose.yaml config
docker compose -f deployments/docker-compose/docker-compose.yaml up --build
```

The stack starts PostgreSQL plus control-plane, AI gateway, S3 gateway, worker, and
scheduler service boundaries. Public probes remain unauthenticated; `/v1/*` and
`/metrics` require the configured credential.

## Kubernetes with Helm

```bash
helm upgrade --install urp deployments/helm/urp \
  --namespace urp-system \
  --create-namespace \
  --set image.repository=ghcr.io/thewisecrab/urp \
  --set image.tag=0.1.0 \
  --set mode=observe \
  --set secrets.create=true \
  --set-string secrets.apiKey="$(openssl rand -hex 32)" \
  --set-string secrets.postgresDsn="postgresql://urp:REPLACE@postgres.example:5432/urp"
```

Production secrets should come from an external secret manager. Set
`secrets.create=false` and reference an existing Secret rather than passing values
on a command line.

Validate before applying:

```bash
helm lint deployments/helm/urp
helm template urp deployments/helm/urp --set secrets.create=false \
  --set secrets.existingSecret=urp-runtime > /tmp/urp-rendered.yaml
```

## Direct Kubernetes manifests

```bash
kubectl apply -f deployments/kubernetes/urp-control-plane.yaml
```

Edit the image tag and secret references before applying. The manifest includes a
non-root security context, read-only root filesystem, probes, resources, a service
account, a disruption budget, and a network policy.

## Cloud reference modules

Terraform reference modules are under:

```text
deployments/terraform/aws
deployments/terraform/azure
deployments/terraform/gcp
```

They define foundational object storage and KMS resources plus platform contracts.
They do not create a complete production network, database, cluster, DNS, or secret
manager environment.

## Required runtime configuration

| Variable | Purpose |
|---|---|
| `URP_LOCAL_API_KEY` or `URP_API_KEYS_JSON` | Required API authentication |
| `URP_MODE` | `observe`, `shadow`, or `enforce` |
| `URP_MANIFEST_STORE` | Local path or PostgreSQL DSN |
| `URP_LEDGER_STORE` | Local path or PostgreSQL DSN |
| `URP_APPROVAL_SIGNING_KEY` | Approval HMAC key for multi-process use |
| `URP_BACKUP_SIGNING_KEY` | Backup integrity key |
| `URP_RELEASE_SIGNING_KEY` | Ed25519 private key for release manifests |

Provider adapters add their own credential variables. Run:

```bash
urp platform validate --target all --require-live
```

## Production boundaries

Before production enforcement, provide:

1. TLS termination, DNS, ingress, and egress policy.
2. Managed PostgreSQL and versioned object storage with tested recovery.
3. Workload identity and secret-manager integration.
4. Capacity, soak, fault, restore, and upgrade tests on representative data.
5. Tenant-specific policy bundles and approval ownership.
6. Observability export, alerting, retention, and incident procedures.
7. Cost baselines and workload-specific verifier service-level objectives.
8. A rollback path to baseline storage and provider routes.

URP's deployment assets are secure starting points, not a substitute for an
organization's production platform controls.
