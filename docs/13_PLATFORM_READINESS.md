# 13 - Platform Readiness

URP now has an explicit platform-readiness layer. The local runtime remains the default safe test path, but the product surface is no longer scoped only to local/mock execution.

## What "All Platforms" Means

URP treats platform support in two levels:

| Level | Meaning | Requires Credentials |
|---|---|---|
| Contract-ready | URP has schemas, APIs, deployment artifacts, adapter expectations, and validation hooks for the target. | No |
| Live-ready | URP can perform live deployment or provider operations against that target. | Yes |

This distinction keeps the default test suite deterministic while making production platform gaps explicit.

## Built-In Platform Targets

Run:

```bash
PYTHONPATH=python python3 -m urp.cli platform matrix
```

Current built-in targets:

- `local`: macOS, Linux, Windows via Python runtime, local chunks, file/SQLite manifests, mock providers.
- `kubernetes`: EKS, AKS, GKE, OpenShift, vanilla Kubernetes, operator-managed deployment.
- `aws`: S3, RDS Postgres, KMS, EKS/ECS/Batch, Bedrock/SageMaker-compatible provider paths, plus an opt-in stdlib S3 SigV4 adapter.
- `azure`: Blob Storage, Azure Database for PostgreSQL, Key Vault, AKS/Container Apps, Azure OpenAI.
- `gcp`: Cloud Storage, Cloud SQL Postgres, Cloud KMS, GKE/Cloud Run, Vertex AI.
- `on_prem`: MinIO/Ceph/NAS, local Postgres, systemd, air-gapped Docker Compose, local model servers.
- `edge`: K3s/MicroK8s/single-node Linux, local exact cache, offline policy cache, delayed ledger sync.
- `openai_compatible`: OpenAI, Azure OpenAI, private OpenAI-compatible model gateways.
- `cicd`: GitHub Actions, GitLab CI, Buildkite, Jenkins, release signing, schema validation.

## Commands

List profiles:

```bash
PYTHONPATH=python python3 -m urp.cli platform list
```

Validate all contract-ready targets:

```bash
PYTHONPATH=python python3 -m urp.cli platform validate --target all
```

Check whether a target is live-ready with credentials:

```bash
PYTHONPATH=python python3 -m urp.cli platform validate --target aws --require-live
```

Without cloud credentials, AWS/Azure/GCP/Kubernetes/on-prem/edge/provider targets should be contract-ready but not live-ready. That is expected.

## REST Surface

The control-plane exposes:

- `GET /v1/platforms`
- `GET /v1/platforms/readiness?target=all`
- `GET /v1/platforms/readiness?target=aws&require_live=true`
- `GET /v1/platforms/matrix`

These routes are present in both the optional FastAPI app and the standard-library service runtime.

## Deployment Artifacts

Platform readiness checks validate the presence of:

- `deployments/docker-compose/docker-compose.yaml`
- `deployments/kubernetes/urp-control-plane.yaml`
- `deployments/kubernetes/urp-multi-region.yaml`
- `deployments/helm/urp/Chart.yaml`
- `deployments/operator/urp-operator.yaml`
- `deployments/terraform/aws/main.tf`
- `deployments/terraform/azure/main.tf`
- `deployments/terraform/gcp/main.tf`
- `deployments/on-prem/docker-compose.airgap.yaml`
- `deployments/on-prem/systemd/urp-control-plane.service`
- `deployments/edge/urp-edge-sidecar.yaml`

## Live Credential Gates

Examples of live-readiness environment gates:

- Kubernetes: `KUBECONFIG`
- AWS: `AWS_REGION`, `AWS_ACCESS_KEY_ID`
- Azure Blob: `AZURE_STORAGE_ACCOUNT`, `AZURE_STORAGE_KEY`, `URP_AZURE_CONTAINER`
- GCP Storage: `GOOGLE_CLOUD_PROJECT`, `URP_GCP_BUCKET` plus application-default or workload identity credentials
- On-prem: `URP_ON_PREM_POSTGRES_DSN`, `URP_ON_PREM_OBJECT_ENDPOINT`
- Edge: `URP_EDGE_SITE_ID`
- OpenAI-compatible providers: `OPENAI_API_KEY`, optional `OPENAI_BASE_URL` or `URP_OPENAI_BASE_URL`
- CI/CD: `CI`

Production deployments should prefer workload identity, managed identity, role assumption, or equivalent mechanisms over long-lived static keys.

The live adapter registry in `python/urp/live_adapters.py` makes missing gates explicit. Current live adapter gates include:

- AWS S3: `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `URP_AWS_BUCKET`
- Postgres manifest store: `URP_POSTGRES_DSN`
- Azure Blob: `AZURE_STORAGE_ACCOUNT`, `AZURE_STORAGE_KEY`, `URP_AZURE_CONTAINER`
- GCP Cloud Storage: `GOOGLE_CLOUD_PROJECT`, `URP_GCP_BUCKET`; `GOOGLE_APPLICATION_CREDENTIALS` is optional when workload identity or application-default credentials are available
- OpenAI-compatible AI: `OPENAI_API_KEY`

## Readiness Invariants

`PYTHONPATH=python python3 -m urp.cli admin readiness` now checks:

- restart persistence;
- exact rehydration after restart;
- policy audit events;
- KMS roundtrip;
- authorization enforcement;
- API authentication and tenant isolation;
- signed approval denial/acceptance gates;
- recursive manifest redaction;
- range-read chunk tamper detection;
- concurrent ledger chain integrity;
- KMS key-material non-disclosure;
- backup/restore rehydration;
- tampered backup detection;
- backup path-traversal rejection;
- HA Kubernetes deployment declaration;
- Postgres backend declaration;
- AWS versioned object backend declaration;
- Azure Blob/Key Vault declaration;
- GCP Cloud Storage/KMS declaration;
- on-prem air-gapped deployment declaration;
- edge sidecar declaration;
- operator manifest declaration;
- multi-region topology declaration;
- all platform profiles contract-ready;
- Kubernetes manifests parse, use pinned images, declare health probes and
  resource bounds, and apply non-root/read-only/capability-drop controls;
- Terraform declares required providers plus object/KMS backends;
- Docker Compose declares stateful backends;
- OpenAPI paths have response declarations and valid local schema refs;
- protobuf services expose typed RPCs for the WorkUnit and platform APIs.

The same checks run through the admin readiness API, so deployment/spec drift is visible without requiring cloud credentials.

## Boundary

This work makes URP platform-contract-ready across the major deployment families and adds opt-in live hooks where deterministic local tests can prove the contract, including OpenAI-compatible HTTP, AWS S3 SigV4, Azure Blob, GCP Cloud Storage, and PostgreSQL persistence. Live deployment still requires credentials, cluster access, cloud accounts, and environment-specific plans. The repository exposes those gates directly instead of hiding them behind a "local only" status.
