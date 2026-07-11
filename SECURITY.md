# Security Policy

Report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/thewisecrab/urp/security/advisories/new)
before public disclosure.
Do not include production API keys, backup signing keys, KMS material, tenant
payloads, prompts, or unredacted manifests in a public issue.

## Security principles

- Exact by default.
- Cross-tenant reuse disabled by default.
- Semantic reduction requires policy and verification.
- Plugins require capability declarations.
- Manifests and ledger events must be protected.
- API identity is configured server-side; token text never grants a role.
- Cache values are accepted only after a server-executed verifier succeeds.
- Backups and release manifests support integrity verification before use.

## Deployment requirements

- Configure `URP_LOCAL_API_KEY` or `URP_API_KEYS_JSON`; do not run
  `URP_AUTH_MODE=disabled` outside an isolated developer machine.
- Use workload identity or a managed secret store for cloud deployments.
- Set `URP_APPROVAL_SIGNING_KEY`, `URP_BACKUP_SIGNING_KEY`, and
  `URP_RELEASE_SIGNING_KEY` from a secret manager when those features cross a
  machine boundary.
- Put TLS termination in front of every non-loopback service endpoint.
- Use PostgreSQL and a versioned object backend for replicated deployments;
  local JSONL/file stores are single-node durability paths.
- Restrict unredacted manifest access to operator/admin roles and retain ledger
  audit data separately from mutable runtime state.

## High severity examples

- unauthorized cache reuse;
- exact-byte rehydration corruption;
- policy bypass;
- plugin sandbox escape;
- manifest tampering;
- legal hold deletion.
- approval replay or signature bypass;
- backup archive traversal or undeclared extraction;
- release manifest path traversal;
- unauthenticated metrics or administrative APIs;
- cross-tenant log, trace, manifest, or approval disclosure.

## Supported versions

| Version | Supported |
|---|---|
| `0.1.x` | Yes |
| Earlier development snapshots | No |

Security fixes are applied to the current `0.1.x` development line. No earlier
development snapshots receive backports before the first stable release.

## Disclosure process

Provide a clear impact statement, affected version or commit, reproduction steps,
and a suggested mitigation when available. Maintainers will coordinate validation,
patching, advisory publication, and credit with the reporter. Do not test against
systems or tenants you do not own or have explicit authorization to assess.
