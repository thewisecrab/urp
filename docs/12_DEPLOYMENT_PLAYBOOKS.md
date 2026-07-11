# 12 — Deployment Playbooks

## Purpose

This document explains how different users adopt URP without disrupting current workflows.

## Universal deployment rule

Start in observe mode. Measure. Then enable exact-safe reductions. Only later enable semantic or approximate reductions with policy and verifiers.

## Local developer playbook

### Goal

Understand URP and reduce repeated local AI calls or test data.

### Steps

1. Install CLI.
2. Run local manifest store.
3. Plan a file.
4. Run AI gateway against a test provider key.
5. Inspect manifest.
6. Inspect ledger.
7. Enable exact cache.

### Commands

```bash
urp init
urp plan --kind byte_object --file sample.log
urp gateway ai --listen :8080 --provider-env OPENAI_API_KEY
urp ledger query --last 20
```

### Success criteria

- developer understands work units;
- exact cache works;
- no production data involved.

## Startup playbook

### Goal

Reduce AI and object storage costs quickly.

### Deployment

```text
Docker Compose
  urp-control
  urp-ai-gateway
  urp-s3-gateway
  postgres
  minio or cloud object backend
```

### Steps

1. Put internal tools behind AI gateway.
2. Enable exact cache.
3. Measure repeated prompts.
4. Add context compiler for RAG app.
5. Put backup bucket behind object gateway.
6. Enable exact dedupe/compression.
7. Add dashboards.

### Policies

- semantic cache off by default;
- exact cache same app only;
- object dedupe same tenant only;
- deletion disabled until reviewed.

## Enterprise observe-only playbook

### Goal

Discover savings without changing behavior.

### Deployment

- traffic mirror;
- proxy in non-invasive mode;
- read-only lakehouse scan;
- AI request logs with redaction;
- manifest store;
- telemetry export.

### Outputs

- savings estimate;
- risk classification;
- duplicate map;
- prompt waste report;
- workload heat map;
- policy recommendations.

### Success criteria

- no application behavior changes;
- owners receive useful reports;
- security signs off on next stage.

## Enterprise exact-safe playbook

### Goal

Enable safe savings for selected workloads.

### Candidate workloads

- backups;
- container layers;
- log archives;
- duplicate objects;
- generated reports;
- repeated AI dev prompts.

### Actions

- whole-object dedupe;
- content-defined chunking;
- zstd compression;
- exact prompt cache;
- context dedupe in shadow mode.

### Required tests

- exact restore;
- range read;
- cache isolation;
- policy denial;
- failover.

## AI platform playbook

### Goal

Reduce model calls and prompt bloat.

### Steps

1. Insert OpenAI-compatible gateway.
2. Run observe mode for all requests.
3. Report task classes and token waste.
4. Enable exact cache for deterministic internal assistants.
5. Enable context compiler for RAG apps.
6. Add model router in shadow mode.
7. Add verifiers.
8. Enable small-model route for accepted classes.
9. Pilot semantic cache.
10. Distill repeated workflows.

### Required controls

- source fingerprints;
- freshness;
- tenant isolation;
- fallback model;
- verifier logs;
- redacted prompt storage.

## Data platform playbook

### Goal

Reduce lakehouse and stream waste.

### Steps

1. Scan object store and catalog.
2. Identify duplicate files and tiny files.
3. Recommend compaction.
4. Run table-native compaction in dev.
5. Verify exact-logical results.
6. Enable snapshot-aware policy.
7. Add lifecycle rules.
8. Add stream archival reduction.

### Do not

- mutate table files outside transaction protocol;
- drop raw data before retention review;
- summarize regulated data silently.

## Regulated enterprise playbook

### Goal

Use URP safely under strict controls.

### Defaults

- exact_bytes global;
- semantic reduction disabled;
- cross-tenant cache disabled;
- local-only manifest store;
- encryption everywhere;
- signed policy bundles;
- legal hold integration;
- manual approvals for lifecycle deletion.

### Rollout

1. observe-only;
2. exact compression/dedupe for non-regulated data;
3. manifest and ledger audit review;
4. limited exact-logical table optimization;
5. semantic reduction only for approved non-record data.

## Edge playbook

### Goal

Reduce network and local AI calls.

### Actions

- compress before upload;
- dedupe chunks locally;
- cache repeated prompts locally;
- summarize low-risk telemetry;
- send manifests when online;
- preserve raw incident data.

### Constraints

- policy cache expiry;
- local key storage;
- offline mode;
- resource caps;
- delayed ledger sync.

## Kubernetes deployment

Components:

- control-plane deployment;
- optional local operator CRD and operator deployment;
- gateway deployment;
- worker deployment;
- scheduler;
- Postgres;
- object store credentials;
- config maps for policies;
- secrets for keys;
- service monitors.

Rollout:

```bash
kubectl apply -f examples/kubernetes/urp-control-plane.yaml
kubectl apply -f deployments/operator/urp-operator.yaml
kubectl apply -f deployments/kubernetes/urp-multi-region.yaml
```

## Production readiness check

Before promoting a local or staging deployment, run:

```bash
PYTHONPATH=python python3 -m urp.cli admin readiness
```

The check uses an isolated local state by default and verifies restart persistence, exact rehydration, authenticated tenant isolation, signed approval gates, recursive redaction, local KMS roundtrip and key-material non-disclosure, range tamper detection, concurrent ledger integrity, backup restore/checksum/path safety, HA and Postgres declarations, versioned cloud object/KMS backends, on-prem and edge artifacts, operator implementation, multi-region topology, API contracts, and all-platform contract readiness.

Run the all-platform matrix:

```bash
PYTHONPATH=python python3 -m urp.cli platform matrix
PYTHONPATH=python python3 -m urp.cli platform validate --target all
PYTHONPATH=python python3 -m urp.cli platform validate --target aws --require-live
```

Targets are contract-ready when schemas, APIs, deployment artifacts, adapter expectations, and validation hooks exist. Targets are live-ready only when the needed credentials or environment bindings are present.

## Cloud deployment patterns

### AWS

- S3 backend;
- EKS;
- RDS Postgres;
- KMS;
- CloudWatch/OpenTelemetry exporter;
- IAM roles for service accounts.

### Azure

- Blob Storage backend;
- AKS;
- Azure Database for PostgreSQL;
- Key Vault;
- Monitor exporter.

### Google Cloud

- Cloud Storage backend;
- GKE;
- Cloud SQL;
- Cloud KMS;
- Cloud Monitoring exporter.

### On-prem

- MinIO/Ceph;
- Kubernetes or systemd;
- Postgres;
- Vault/HSM;
- local model server;
- Prometheus/Grafana.

## Migration plan

### Existing object bucket

1. observe reads/writes;
2. build duplicate map;
3. select prefix;
4. enable exact-safe writes;
5. backfill old objects asynchronously;
6. verify sample restores;
7. update lifecycle.

### Existing AI app

1. switch base URL to URP gateway;
2. run pass-through;
3. enable metrics;
4. enable exact cache;
5. enable context compiler;
6. shadow model router;
7. enforce router with fallback.

### Existing lakehouse

1. catalog scan;
2. recommendations only;
3. dev table optimization;
4. snapshot verification;
5. production canary;
6. rollback test.

## Rollback procedures

### Object gateway rollback

- switch DNS/endpoint to original object store;
- keep manifest store read-only;
- rehydrate affected objects if needed;
- disable lifecycle jobs.

### AI gateway rollback

- switch base URL to provider;
- disable semantic cache;
- export compute manifests;
- preserve ledger for audit.

### Policy rollback

- publish previous bundle;
- mark bad bundle deprecated;
- re-evaluate affected manifests;
- emit rollback event.

## Enterprise change management

Required artifacts:

- architecture diagram;
- threat model;
- data flow;
- policy defaults;
- rollback plan;
- SLOs;
- test evidence;
- owner signoff.

## Adoption success checklist

- observe mode data collected;
- exact restore tested;
- security policy approved;
- metrics exported;
- rollback tested;
- owners trained;
- cache isolation tested;
- semantic features disabled or approved;
- incident runbook written.

## Ideal-state adoption

URP becomes part of platform golden paths:

- new object buckets default through URP;
- AI apps default through URP gateway;
- batch jobs declare deadlines;
- training jobs declare dataset manifests;
- tables include URP optimization metadata;
- developers inspect manifests in CI.
