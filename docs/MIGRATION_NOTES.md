# Migration Notes

## Source Package Consolidation

The original handoff packages were preserved under:

- `archive/source_packages/urp_quality_product_package`
- `archive/source_packages/urp_oss_ideal_state_package`

The canonical implementation now lives at the repository root.

## Public Model

The current public model uses:

- `WorkUnit`
- `Contract`
- `Plan`
- `PlanAction`
- `Manifest`
- `LedgerEvent`
- `PolicyDecision`
- `VerificationResult`

The OSS-era `ResourceRef`, `ResourceContract`, and `ReductionPlan` names are
treated as legacy inputs. Their useful behaviors were migrated into the WorkUnit
model and covered by root tests.

## Runtime Layout

- Python runtime moved from `src/python/urp` to `python/urp`.
- Go SDK moved to `go`; `go/urp` re-exports the public SDK surface for the
  plan's named compatibility path.
- TypeScript SDK moved to `typescript`.
- Rust chunker moved to `crates/urp-chunker`; `crates/urp-core` and
  `crates/urp-gateway-s3` provide tested local contract crates for the
  blueprint's Rust package families.
- Local service boundaries live under `services`.

## Compatibility Defaults

- Unknown data defaults to exact preservation.
- Cross-tenant cache and dedupe remain disabled.
- Semantic, approximate, lossy, deletion, and distillation reducers require
  explicit policy context and verifiers.
- External cloud/provider integrations are adapters and are skipped unless the
  caller supplies credentials and environment-specific configuration.

## Security And API Changes

- REST routes under `/v1/*` and `/metrics` now require a configured bearer
  token or `X-API-Key`. Prefix-shaped keys such as `admin:name` no longer assign
  roles. Configure `URP_LOCAL_API_KEY` or `URP_API_KEYS_JSON`.
- Tenant identity comes from the authenticated principal. A body or query
  cannot authorize cross-tenant access.
- Manifest views are role-aware. Viewer and gateway roles receive redacted
  logical references, cache keys, sensitive nested fields, and physical chunk
  references.
- Manifest rehydration and S3 Get/range endpoints now return raw
  `application/octet-stream` bytes. TypeScript and Go SDK methods return binary
  values directly.
- Cache store APIs no longer accept `verifier_passed`. Callers submit a
  supported verifier specification and the server evaluates the value.
- Policy rules that require approval use short-lived signed approval records
  bound to tenant, contract, policy bundle, and optionally WorkUnit id.
- Failed AI verification after fallback now returns `verifier_failed`; rejected
  output is not returned, manifested, or cached.

## Persistence And Operations

- Chunk records persist the actual codec (`zstd` or the stdlib `zlib` fallback)
  and verify each restored chunk before full or range reads.
- Exact and semantic caches support durable SQLite storage, TTL expiry, tenant
  and namespace isolation, source fingerprint checks, and output revalidation.
- Local KMS envelopes use AES-256-GCM. Backup format `urp.backup.v2` validates
  declared entries, sizes, checksums, path containment, links, duplicates, and
  optional HMAC signatures before staged restore.
- PostgreSQL manifest and ledger backends are opt-in through
  `URP_MANIFEST_STORE` and `URP_LEDGER_STORE`.
- Release attestations use Ed25519. `URP_RELEASE_SIGNING_KEY` must be a
  base64-encoded 32-byte private key; use `urp release verify` to enforce it.
- Terraform provider locks are committed for AWS, Azure, and GCP modules.

## Execution Modes

- `observe` records policy and plan evidence without storing a rehydratable
  reduced output.
- `shadow` executes into an isolated namespace and records a superseded
  manifest.
- `enforce` executes the accepted plan and requires verifier success before the
  output can be used.
