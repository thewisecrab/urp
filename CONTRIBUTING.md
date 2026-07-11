# Contributing

Thank you for contributing to URP.

## Before you start

Read:

1. README.md
2. docs/00_START_HERE.md
3. docs/03_UNIFIED_WORK_UNIT_AND_MANIFEST_MODEL.md
4. docs/06_POLICY_SECURITY_COMPLIANCE.md

## Contribution rules

- Preserve the single URP lifecycle.
- Add tests for every behavior change.
- Do not introduce semantic reduction without policy and verifier support.
- Do not weaken tenant isolation.
- Update schemas and docs when public fields change.
- Add ledger events for new actions.
- Add metrics for new hot-path behavior.

## Pull request checklist

- [ ] Tests pass.
- [ ] Docs updated.
- [ ] Security impact considered.
- [ ] Manifest impact considered.
- [ ] Policy impact considered.
- [ ] Backward compatibility considered.

## Required checks

```bash
python3 -m pip install -e ".[dev]"
python3 -m ruff check python tests
python3 -m pytest -q
npm test --prefix typescript
(cd go && go test -race ./...)
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
python3 -m urp.cli admin readiness
```

Cloud credentials are not required for the default suite. Changes to a live
adapter must add injected-client or protocol-level tests and keep live calls
opt-in.
