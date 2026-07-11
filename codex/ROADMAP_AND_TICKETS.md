# Roadmap and Tickets

> Historical initial roadmap. Completed behavior is tracked by
> `codex/ACCEPTANCE_CHECKLIST.md`, tests, and production readiness checks.

## Milestone 0: Trustworthy skeleton

- Core dataclasses/types.
- Policy evaluation.
- Planner.
- CLI.
- Unit tests.
- Manifest schema.

## Milestone 1: Exact object MVP

- S3-compatible minimal Put/Get/Head.
- Chunk store.
- Rehydration.
- zstd plugin.
- Manifest store.
- Ledger.

## Milestone 2: AI gateway MVP

- OpenAI-compatible chat endpoint.
- Exact cache.
- Context compiler v0.
- Model router v0.
- Mock provider.
- Compute manifests.

## Milestone 3: Security and policy

- Authn/authz.
- Policy bundles.
- Legal hold.
- Cache isolation.
- Plugin descriptors.
- Redacted manifests.

## Milestone 4: Observability and conformance

- Metrics.
- Traces.
- Dashboards.
- S3 conformance subset.
- AI conformance subset.
- Benchmark runner.

## Milestone 5: Advanced reductions

- Semantic cache.
- Lakehouse optimizer.
- Stream observe adapter.
- Training reducer.
- Checkpoint delta store.
- Energy scheduler.

## Milestone 6: Production

- HA deployments.
- Postgres backends.
- KMS integration.
- Operator.
- Multi-region.
- Disaster recovery.
- Release process.
