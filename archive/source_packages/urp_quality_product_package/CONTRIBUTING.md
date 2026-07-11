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
