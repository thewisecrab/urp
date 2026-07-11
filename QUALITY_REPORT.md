# Quality Report

Generated: 2026-07-11

URP is implemented as a local-ideal, multi-language monorepo. The default suite
uses no cloud or model-provider credentials; live adapters remain explicit
credential gates.

## Current Gates

- Python: 86 tests pass under Python 3.13 with `ResourceWarning` promoted to an
  error; statement coverage is 74.73% and CI enforces a 70% floor across Python
  3.10-3.14.
- Python lint: Ruff passes for `python`, `tests`, and publication scripts.
- TypeScript: strict build, authenticated/binary SDK tests, and npm package
  dry-run pass.
- Go: `gofmt` is clean and `go test -race ./...` passes.
- Rust: `cargo fmt --check`, clippy with warnings denied, and all eight workspace
  tests pass.
- Packaging: the Python wheel installs in a clean venv outside the checkout,
  finds installed schemas, and completes an exact-byte CLI execution.
- Terraform: formatting and provider-backed validation pass for AWS, Azure, and
  GCP modules; dependency lock files are committed.
- Kubernetes: Helm lint and both existing-secret and chart-managed-secret render
  paths pass with non-root, read-only, probe, resource, persistence, disruption,
  autoscaling, and network-policy controls represented in the chart.
- Documentation: MkDocs strict build passes with canonical URLs, OpenGraph,
  Twitter metadata, JSON-LD, sitemap, `robots.txt`, and `llms.txt`; the white
  paper renders to a visually inspected 14-page A4 PDF.
- CI supply chain: all workflows pass `actionlint`; actions are digest-pinned,
  GitLeaks scans pushes and pull requests, while release automation generates
  checksums, an SBOM, attestations, packages, a GitHub release, and a
  multi-architecture GHCR image.
- Product readiness: all built-in platform profiles are contract-ready and the
  production readiness suite passes authentication, tenant isolation, signed
  approvals, redaction, chunk tamper detection, concurrent ledger integrity,
  KMS non-disclosure, backup restore/integrity/path safety, specs, and deployment
  structure.
- Release integrity: active-tree digests are root-contained and self-excluding;
  optional Ed25519 attestations verify through the CLI.

## Security Properties Exercised

- Server-configured API identities and tenant-bound RBAC.
- Role-aware recursive manifest redaction.
- Exact-byte and per-range chunk verification with recorded codecs.
- Cross-tenant cache, dedupe, manifest, log, ledger, approval, and object denial.
- Server-executed cache verification; client booleans are not trusted.
- Policy and signed-approval gates for advanced execution.
- Rejected AI fallback output is neither returned nor cached.
- Private local state files, atomic writes, locked JSONL appends, and SQLite WAL
  persistence with deterministic connection cleanup.
- Backup and release archive/path traversal rejection.
- Digest-pinned plugin entrypoints with explicit trust and operation contracts.

## Evidence

- `TEST_RESULTS.md`
- `tests/conformance/test_hardening.py`
- `python/urp/production.py`
- `python/urp/deployment_validation.py`
- `python/urp/spec_validation.py`
- `examples/live/run_live_examples.py`
- `docs/WHITE_PAPER.md`
- `docs/assets/URP-White-Paper-v1.0.pdf`
- `deployments/helm/urp/`

## Environment Boundary

Docker is not installed on this workstation. Dockerfile and Compose structure
are validated locally by readiness checks; GitHub Actions performs Compose
configuration and image-build gates. Live cloud, PostgreSQL, Kubernetes, and
model-provider operations require their documented credentials and are not
represented as locally executed.
