# Security Policy

Report vulnerabilities privately to the maintainers before public disclosure.

## Security principles

- Exact by default.
- Cross-tenant reuse disabled by default.
- Semantic reduction requires policy and verification.
- Plugins require capability declarations.
- Manifests and ledger events must be protected.

## High severity examples

- unauthorized cache reuse;
- exact-byte rehydration corruption;
- policy bypass;
- plugin sandbox escape;
- manifest tampering;
- legal hold deletion.

## Supported versions

The project will define supported versions after the first stable release.
