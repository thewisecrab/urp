# Test Results

Generated: 2026-07-11

## Passed Locally

```text
python3 -m pytest -W error::ResourceWarning --cov=urp --cov-fail-under=70
86 passed; 74.73% total statement coverage

python3 -m ruff check python tests scripts
All checks passed

npm test  # typescript/
2 passed; strict TypeScript build passed

npm pack --dry-run  # typescript/
6 package files; dry-run passed

go test -race ./...  # go/
passed

cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
8 passed

terraform fmt -check -recursive deployments/terraform examples/terraform
terraform validate  # AWS, Azure, GCP after backend-disabled init
all three provider graphs passed using native ARM Terraform 1.14.6

python3 -m build
clean-venv schema lookup and exact-byte CLI smoke
wheel and sdist passed without build warnings

actionlint -no-color
all seven GitHub Actions workflows passed static validation

gitleaks git . --staged --config .gitleaks.toml
no secrets found in the staged public snapshot

helm lint deployments/helm/urp
helm template  # existing-secret and chart-managed-secret modes
both render paths passed

python3 -m mkdocs build --strict
documentation site, canonical metadata, sitemap, robots.txt, llms.txt, and JSON-LD passed

python3 scripts/render_whitepaper.py
14-page A4 PDF rendered; text, metadata, links, and page images inspected

python3 -m urp.cli platform validate --target all
all 9 built-in targets contract-ready

python3 -m urp.cli admin readiness
all readiness checks passed
```

## Additional Release Gates

```bash
python3 -m urp.cli plugin conformance --all-packages
python3 -m urp.cli benchmark run --suite object-exact-v1
python3 -m urp.cli conformance ai
python3 examples/live/run_live_examples.py --reset
python3 -m urp.cli release metadata
python3 -m urp.cli release sign --output PACKAGE_SHA256.json
python3 -m urp.cli release verify --manifest PACKAGE_SHA256.json
```

These cover exact object restore and ranges, legal holds, mock AI exact-cache
hits and fallback rejection, context application, high-risk routing, base64
embeddings, local domain adapters, manifests, ledger-chain verification,
reports, plugins, generated package metadata, and release integrity.

The `local-all-v1` benchmark ran all four deterministic local suites. The live
evidence runner emitted four examples, four manifests, 24 ledger events, exact
object rehydration, an `exact_hit` on the second AI request, and a valid ledger
chain without external services.

## Not Executed Locally

Docker Compose configuration and image building were not run because Docker is
not installed on this workstation. They remain required GitHub Actions checks.
No live cloud, Kubernetes, PostgreSQL, or model-provider operation was attempted
without credentials.

## Later run (2026-10-29)

This section does not replace the 2026-07-11 receipt above. That receipt still
records 86 passes and a 14-page PDF. The committed file
`docs/assets/URP-White-Paper-v1.0.pdf` currently contains 16 `/Type /Page`
objects. This run did not regenerate the PDF.

Environment: Linux 6.12.94+ x86_64, CPython 3.12.3, pytest 9.2.0, hypothesis
6.170.13, ruff 0.15.21. Started 2026-10-29T13:43:05Z, finished
2026-10-29T13:43:38Z.

```text
.venv/bin/ruff check python tests
All checks passed

.venv/bin/python -m pytest -W error::ResourceWarning --cov=urp --cov-report=term-missing --cov-fail-under=70 -q --tb=no
115 passed in 32.59s
Required test coverage of 70% reached. Total coverage: 75.47%
```

Ruff 0.17.3, checked the same day, fails on pre-existing modules because its
default rule set adds pyupgrade, import sorting, and E501. The dev extra pins
ruff==0.15.21, which is also the publication workflow pin. Touched files pass
that pin.

Kubernetes and Helm were not installed. No live provider call was made.

## Later run (2026-10-29, second pass)

This does not replace the 2026-07-11 receipt or the earlier 2026-10-29 section
(115 passed). Environment: Linux 6.12.94+ x86_64, CPython 3.12.3, pytest 9.2.0,
hypothesis 6.170.13, ruff 0.15.21. Started 2026-10-29T13:55:42Z, finished
2026-10-29T13:56:16Z.

```text
.venv/bin/ruff check python tests
All checks passed

.venv/bin/python -m pytest -W error::ResourceWarning --cov=urp --cov-report=term-missing --cov-fail-under=70 -q --tb=line
119 passed in 33.13s
Required test coverage of 70% reached. Total coverage: 75.53%
```

The checked-in portfolio scenario, with `input_pricing` set to `list_price`,
still returns gross monthly savings 7798.56, operating-cost net 5298.56, and
payback 5.66 months. Helm, Terraform, and Compose were not installed. No
container was run as a deployment.

At 2026-10-29T13:56:26Z: `npm test --prefix typescript` passed (2 tests);
`cd go && go test -race ./...` passed (cached `ok`); `cargo fmt --all -- --check`,
`cargo clippy --workspace --all-targets --offline -- -D warnings`, and
`cargo test --workspace --offline` passed (8 crate tests).
