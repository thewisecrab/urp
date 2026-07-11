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
