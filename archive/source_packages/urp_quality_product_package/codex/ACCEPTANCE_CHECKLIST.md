# Acceptance Checklist

## Repository

- [ ] License present.
- [ ] README quickstart works.
- [ ] CI runs tests.
- [ ] Formatting configured.
- [ ] Security policy present.
- [ ] Contribution guide present.

## Core

- [ ] WorkUnit schema implemented.
- [ ] Manifest schema implemented.
- [ ] Policy schema implemented.
- [ ] Ledger event schema implemented.
- [ ] IDs use stable prefixes.
- [ ] JSON serialization tested.

## Policy

- [ ] Exact default.
- [ ] Legal hold override.
- [ ] Cross-tenant cache denied.
- [ ] Cross-tenant dedupe denied.
- [ ] Semantic transforms denied unless allowed.
- [ ] Explain output includes matched rules.

## Data path

- [ ] Hashing.
- [ ] Chunking.
- [ ] Chunk store.
- [ ] Compression plugin interface.
- [ ] Exact rehydration.
- [ ] Restore verifier.
- [ ] Manifest write.
- [ ] Ledger events.

## AI path

- [ ] OpenAI-compatible request parsing.
- [ ] Exact cache.
- [ ] Tenant isolation.
- [ ] Context dedupe.
- [ ] Model router.
- [ ] Fallback provider.
- [ ] Verifier hook.
- [ ] Compute manifest.

## Security

- [ ] No raw prompts in default logs.
- [ ] Manifest redaction mode.
- [ ] Plugin descriptor validation.
- [ ] Policy override audited.
- [ ] Cache source fingerprint checks.

## Observability

- [ ] Metrics endpoint.
- [ ] Trace ids.
- [ ] Ledger query.
- [ ] Savings report.
- [ ] Error codes.

## Release

- [ ] Conformance tests.
- [ ] Benchmark suite.
- [ ] Migration notes.
- [ ] Signed release artifacts.
