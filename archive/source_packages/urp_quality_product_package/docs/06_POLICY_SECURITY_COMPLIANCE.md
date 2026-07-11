# 06 — Policy, Security, Compliance, and Trust

## Purpose

URP reduces infrastructure waste by changing how data and AI work units are stored, routed, cached, transformed, summarized, or deleted. That makes policy and trust central, not optional.

The system must be safe before it is clever.

## Policy model

A URP policy answers five questions:

1. What is this work unit?
2. What must be preserved?
3. What is allowed?
4. What is forbidden?
5. What must be proven?

## Policy inputs

Policy may inspect:

- tenant;
- namespace;
- application id;
- user id;
- service account;
- region;
- environment;
- data classification;
- work unit kind;
- schema;
- object tags;
- bucket/table/topic;
- AI task type;
- model/provider;
- legal hold status;
- retention class;
- source fingerprint;
- latency budget;
- request purpose;
- plugin trust level.

## Policy outputs

Policy returns:

- effective contract;
- transform allowlist;
- transform denylist;
- cache domain;
- dedupe domain;
- retention schedule;
- rehydration requirement;
- verifier requirements;
- model allowlist;
- scheduler constraints;
- ledger requirements;
- approval requirements.

## Example policy

```yaml
apiVersion: urp.dev/v1
kind: ReductionPolicy
metadata:
  name: default-enterprise-policy
spec:
  defaults:
    contract: exact_bytes
    semanticReduction: deny
    crossTenantDedupe: deny
    crossTenantCache: deny
  rules:
    - name: exact-finance-ledger
      match:
        tags:
          data_class: financial_ledger
      contract: exact_bytes
      allow:
        transforms: [hash, chunk, dedupe_same_tenant, zstd]
      deny:
        transforms: [semantic_summary, lossy_transcode, approximate_quantization]
      require:
        verifiers: [sha256_restore]
        retention: never_delete
    - name: support-ai-semantic-cache
      match:
        kind: prompt_request
        namespace: support-ai
      contract: semantic
      allow:
        transforms: [exact_cache, semantic_cache, context_compile, model_route]
      require:
        verifiers: [source_consistency, freshness_check]
        max_cache_age: 24h
```

## Policy evaluation principles

### Strictest rule wins

A legal hold should override cost-saving rules. A regulated data class should override a namespace default.

### Deny unknown semantic reduction

Unknown data may be compressed and deduped exactly. It must not be summarized, approximated, or semantically substituted unless explicitly allowed.

### Deterministic evaluation

The same input and policy bundle should produce the same decision.

### Versioned policy bundles

Every manifest and ledger event should record the policy bundle id.

### Explainability

Policy results should include matched rules and denied actions.

## Security domains

URP needs explicit domains.

### Tenant domain

Boundary for data ownership and cache sharing.

### Dedupe domain

Boundary in which duplicate chunks may be reused.

Default: same tenant and policy domain only.

### Cache domain

Boundary in which AI or data cache entries may be reused.

Default: same tenant, same application, same source fingerprints, same policy.

### Encryption domain

Boundary for keys and plaintext visibility.

### Plugin trust domain

Boundary for which plugins may run against which data.

### Network domain

Boundary for where data and compute may move.

## Cross-tenant dedupe risk

Cross-tenant dedupe can leak information through timing, storage accounting, or existence tests. URP must disable cross-tenant dedupe by default.

If an operator wants cross-tenant dedupe:

- require explicit policy;
- use side-channel mitigations;
- aggregate billing carefully;
- avoid exposing hit/miss timing;
- consider convergent encryption risks;
- record high-risk ledger events.

## Semantic cache risk

Semantic cache can return an answer that seems right but is stale, unauthorized, or contextually wrong.

Mitigations:

- tenant isolation;
- source fingerprinting;
- freshness windows;
- permission checks;
- task-specific similarity thresholds;
- verifiers;
- high-risk domain blocklist;
- fallback to model;
- clear ledger event.

## Prompt privacy

AI requests often contain sensitive data.

URP should:

- avoid logging full prompts by default;
- store prompt hashes and redacted summaries;
- encrypt prompt cache entries;
- allow local-only deployments;
- support no-retention mode;
- preserve provider privacy constraints;
- give admins configurable retention.

## Encryption

### Reduce before encrypting

Compression and dedupe work best before encryption, because encrypted data should look random.

Safe architecture:

```text
plaintext inside trusted boundary
-> reduce exactly
-> encrypt chunks/manifests/cache records
-> store physical data
```

### Client-side encryption

If clients encrypt before URP sees data, URP can still:

- store exact;
- hash ciphertext;
- dedupe exact ciphertext within allowed domain;
- lifecycle by metadata;
- observe size and access patterns.

But it cannot semantically reduce or effectively compress.

### Key management

URP should integrate with:

- cloud KMS;
- HashiCorp Vault;
- on-prem HSM;
- Kubernetes secrets for dev only;
- envelope encryption.

Manifest secrets should be separated from metadata where possible.

## Manifest security

Manifest fields can leak sensitive information.

Protect:

- logical refs with sensitive names;
- source fingerprints;
- policy tags;
- prompt summaries;
- model outputs;
- user ids;
- derived facts.

Support:

- encrypted fields;
- redacted export;
- role-based manifest views;
- signed manifests;
- tamper-evident ledger.

## Plugin security

Plugins can be dangerous because they may see plaintext.

Requirements:

- capability declaration;
- least privilege;
- sandboxing option;
- signed plugin packages;
- dependency scanning;
- resource limits;
- deterministic mode for policy-sensitive transforms;
- no network access by default for high-risk transforms;
- conformance tests.

## Identity and access

URP should support:

- API keys for dev;
- mTLS for services;
- OIDC/OAuth for users;
- workload identity in Kubernetes;
- cloud IAM integration;
- SCIM or directory sync for enterprise;
- service-account policies.

## Authorization

Authorization checks should exist for:

- work unit intake;
- manifest read;
- raw rehydration;
- semantic cache use;
- policy override;
- plugin install;
- transform execution;
- model route;
- deletion/tombstone;
- ledger query.

## Compliance support

URP should not claim certification by default. It should provide features that make certification and audits easier.

Relevant capabilities:

- retention policies;
- legal hold;
- deletion proof;
- audit ledger;
- manifest lineage;
- access logs;
- encryption;
- data residency;
- role separation;
- policy versioning;
- eDiscovery export;
- restore testing.

## Regulated data classes

Default recommendations:

| Data class | Default contract | Semantic reduction | Cache sharing |
|---|---|---:|---:|
| financial ledger | exact_bytes | deny | same dataset only |
| medical record | exact_bytes | deny unless approved | highly restricted |
| legal record | exact_bytes | deny | restricted |
| security incident | exact_bytes hot, exact_logical warm | restricted | same team |
| debug logs | exact hot, semantic after window | allow by policy | same tenant |
| public docs | exact_logical or semantic | allow | broader |
| marketing media | bounded_approx | allow | same org |
| AI prompt with PII | semantic only with strict policy | restricted | no cross-app default |

## Legal hold

Legal hold must block:

- deletion;
- tombstoning;
- semantic-only retention;
- lossy transformation if raw is not preserved;
- lifecycle expiration;
- cache eviction when required for evidence.

Legal hold changes must produce ledger events.

## Data minimization

URP can help with privacy by deleting or summarizing low-value data, but only under policy.

The system should distinguish:

- operational minimization;
- legal retention;
- customer deletion requests;
- analytics aggregation;
- AI training exclusion;
- derived artifact deletion.

## AI safety and output trust

For AI output, URP must not treat cache/routing as only a cost problem.

Required controls:

- task classification;
- domain risk;
- source grounding;
- output schema validation;
- tool verification;
- fallback on uncertainty;
- human approval for high-risk automation;
- policy hooks for safety systems.

## Audit trail examples

Semantic cache hit event:

```json
{
  "event_type": "ai.semantic_cache.accepted",
  "similarity": 0.94,
  "source_fingerprints_match": true,
  "freshness_seconds": 318,
  "verifier": "support_policy_source_consistency@1.2.0",
  "fallback_available": true
}
```

Denied transform event:

```json
{
  "event_type": "policy.transform.denied",
  "transform": "semantic_summary",
  "reason": "effective_contract_exact_bytes",
  "matched_rule": "finance-ledger-exact"
}
```

## Incident response

URP security incidents may include:

- unauthorized cache reuse;
- manifest tampering;
- plugin compromise;
- policy misconfiguration;
- verifier bypass;
- data rehydration failure;
- cross-tenant side channel;
- stale semantic answer.

Runbook steps:

1. freeze policy bundle;
2. disable affected plugins;
3. bypass semantic cache;
4. force exact fallback;
5. query ledger;
6. identify affected work units;
7. rehydrate originals where needed;
8. rotate keys;
9. publish incident report;
10. add conformance tests.

## Threat model

### Adversaries

- malicious tenant;
- compromised app service;
- malicious plugin;
- insider with partial access;
- external attacker;
- careless administrator.

### Assets

- raw payloads;
- manifests;
- cache entries;
- ledger;
- policies;
- keys;
- model outputs;
- source fingerprints;
- dedupe indexes.

### Attack paths

- infer data existence from dedupe;
- retrieve unauthorized cache entry;
- install malicious transform;
- alter manifest rehydration path;
- weaken policy;
- poison semantic cache;
- poison training reducer;
- exploit prompt logging;
- abuse model router.

## Required security tests

- cross-tenant cache rejection;
- cross-tenant dedupe rejection;
- legal hold blocks deletion;
- exact contract blocks semantic transform;
- stale source invalidates semantic cache;
- plugin capability enforcement;
- manifest signature verification;
- redacted manifest view;
- policy override audit event;
- fallback on verifier failure.

## Open-source trust posture

The project should be transparent about risks. Avoid exaggerated claims. Publish threat models, conformance tests, and security advisories.

## Security invariant

URP must never silently trade correctness, privacy, or compliance for savings.
