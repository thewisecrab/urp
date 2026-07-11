# Changelog

All notable project changes are documented here. URP follows semantic versioning
after the first stable release; pre-1.0 minor versions may include public interface
changes with migration notes.

## [Unreleased]

### Planned

- Production trace studies and distributed scale benchmarks.
- Managed-store reference implementations and recovery exercises.
- Additional task-specific semantic verifier suites.

## [0.1.0] - 2026-07-11

### Added

- Canonical WorkUnit, Contract, Plan, Manifest, LedgerEvent, PolicyDecision, and
  VerificationResult model.
- Exact object chunking, compression, tenant isolation, checksum verification,
  range rehydration, and multipart operations.
- OpenAI-compatible AI gateway, exact and semantic cache interfaces, context
  compiler, model router, embeddings, and safe provider fallback.
- Policy bundles, signed approvals, legal-hold enforcement, plugin capabilities,
  redacted exports, encrypted envelopes, backup verification, and release digests.
- Local adapters for SQL, lakehouse, streams, OTLP, training, vectors, edge, and
  CI/CD plus opt-in cloud and provider adapters.
- REST/OpenAPI, protobuf, CLI, TypeScript, Go, and Rust surfaces.
- Docker, Docker Compose, Kubernetes, Helm, Terraform, on-premises, edge, and
  multi-region deployment references.
- Reproducible impact calculator with low, base, and high scenario inputs.
- Evidence-based white paper, PDF publication workflow, and searchable docs site.

[Unreleased]: https://github.com/thewisecrab/urp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/thewisecrab/urp/releases/tag/v0.1.0
