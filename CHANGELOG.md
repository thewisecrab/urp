# Changelog

All notable project changes are documented here. URP follows semantic versioning
after the first stable release; pre-1.0 minor versions may include public interface
changes with migration notes.

## [Unreleased]

### Changed

- `input_pricing` is required. Omitting it no longer prices avoided input tokens
  at the full list rate. The checked-in portfolio scenarios set `list_price`
  explicitly so the published $7,798.56 / $5,298.56 / 5.66-month figures still
  reproduce. `effective_blended` still requires operator-supplied cache shares.
- `financial_impact.gross_net_of_operating_cost_monthly` is the same value as
  `net_monthly_savings`. It is gross avoided cost minus operating cost, not a
  change in total spend. The old key remains.

### Added

- Draft v1.1 impact accounting: flagged list-price input rates, optional
  operator-supplied prompt-cache read/write pricing, gross attributional labels,
  a rebound indicator from caller-supplied totals, and an operator-supplied
  fixed-plus-per-token energy model. No default energy intensity.
- Gateway ledger and trace records for provider-reported prompt-cache usage when
  those response fields are present.
- Cache-breakpoint preservation in the context compiler. Budget truncation stays
  off unless policy and the request both opt in.
- Local `DecisionBackend` interface around the existing keyword router and
  lexical semantic-cache scorer. No provider client was added.
- Hypothesis restore checks and a frozen manifest corpus.
- `URPError` still rejects field writes after init, and allows Starlette to clear
  `__traceback__` on a handled exception.

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
