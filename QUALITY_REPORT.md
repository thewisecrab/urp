# Quality Report

Generated: 2026-07-11

URP is implemented as a local-ideal, multi-language monorepo. The default suite
uses no cloud or model-provider credentials; live adapters remain explicit
credential gates.

## Current gates (2026-10-29)

This section is the latest local run. The 2026-07-11 "Current Gates" text below
is unchanged.

Environment: Linux 6.12.94+ x86_64, CPython 3.12.3, pytest 9.2.0, hypothesis
6.170.13, ruff 0.15.21. Python command window 2026-10-29T13:55:42Z to
2026-10-29T13:56:16Z.

- Python: `119 passed` in 33.13s. Statement coverage 75.53% (`--cov-fail-under=70`).
  Command: `.venv/bin/python -m pytest -W error::ResourceWarning --cov=urp --cov-report=term-missing --cov-fail-under=70 -q --tb=line`
- Python lint: `.venv/bin/ruff check python tests` passed (ruff 0.15.21).
- The published portfolio scenario with explicit `input_pricing: "list_price"`
  still returns gross monthly savings 7798.56, net of operating cost 5298.56,
  and payback 5.66 months.
- Helm, Terraform, and Compose were not installed. No cluster or cloud apply
  was run. No container image was run as a deployment in this session.
- 2026-10-29T13:56:26Z: `npm test --prefix typescript` passed (2 tests, `tsc` build).
  `cd go && go test -race ./...` passed (`ok`, cached from the race run earlier
  the same day; `go/urp` has no test files). `cargo fmt --all -- --check`,
  `cargo clippy --workspace --all-targets --offline -- -D warnings`, and
  `cargo test --workspace --offline` passed (2 + 2 + 4 tests).

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

## Addendum (2026-10-29)

The 2026-07-11 text above is unchanged. A later Python run is in `TEST_RESULTS.md`
(115 passed, 75.47% coverage, ruff 0.15.21). The committed white-paper PDF has
16 page objects; the 14-page sentence above is the original receipt. Kubernetes
manifests were still not installed on a cluster.
