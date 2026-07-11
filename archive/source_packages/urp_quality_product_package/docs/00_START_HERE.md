# 00 — Start Here

This document tells a new engineer, contributor, investor, enterprise buyer, or Codex agent how to read the package.

## The correction this package makes

A prior draft used artificial length targets. This package removes arbitrary line-count requirements. The goal is now usefulness, precision, and buildability. Every document has a specific job. Repetition is kept only where it improves standalone readability.

## URP in one paragraph

Universal Reduction Plane is a single open-source product that sits between existing applications and existing infrastructure. It observes or intercepts data and AI work units, determines what must be preserved, applies safe reduction methods, verifies the outcome, records a manifest, and emits audit events. It reduces storage pressure, data movement, AI inference waste, redundant training, cache misses, and peak compute demand while preserving compatibility with S3, POSIX, SQL, lakehouse formats, streams, OpenAI-compatible APIs, model servers, Kubernetes, and developer SDKs.

## The order to read

1. Product explainer for market, user, and value.
2. Ideal-state architecture for the final system.
3. Work unit and manifest model for the universal abstraction.
4. Reduction and AI algorithms for the core technical engine.
5. Adapter catalog for platform compatibility.
6. Policy/security/compliance for safe enterprise adoption.
7. APIs/schemas/protocols for implementation.
8. Codex blueprint for build tasks.
9. Observability and benchmarks for proving value.
10. Research landscape for grounding decisions.
11. Open-source governance and adoption.
12. Deployment playbooks.

## The central design decision

Do not split URP into a "data plane" and an "AI plane" product. There is only one URP. The internal modules can be separated for code organization, but the product abstraction is singular:

```text
Work Unit + Contract + Policy -> Plan -> Execute -> Verify -> Manifest + Ledger
```

The same lifecycle applies to a 16 MiB object chunk, a Parquet row group, a stream segment, a prompt request, an embedding batch, an adapter training run, and a model checkpoint.

## What to build first

Build the thin vertical slice that proves the universal model:

- Accept a work unit.
- Classify it.
- Resolve a policy.
- Produce a plan.
- Execute simple exact-safe transforms.
- Verify restoration.
- Store a manifest.
- Emit ledger events.
- Expose metrics.
- Provide SDK and CLI usage.

The first production-capable target should be:

```text
S3-compatible object gateway + OpenAI-compatible AI gateway + shared manifest/ledger/policy system
```

That is enough to prove URP as one product, not a collection of isolated optimizers.

## Repository quality bar

A contributor should be able to:

- run tests locally;
- inspect a manifest;
- understand why URP made a decision;
- disable any reducer;
- run in observe-only mode;
- write a plugin without changing core code;
- see reduction ratios, cache hit rates, and verifier results;
- compare URP outputs against baseline infrastructure;
- perform a clean rollback.


## Core glossary

| Term | Meaning |
|---|---|
| URP | Universal Reduction Plane, one product that reduces storage, data movement, AI compute, training waste, inference waste, and peak energy demand without forcing application rewrites. |
| Work Unit | The universal input abstraction. A work unit may be a file, object, row group, stream segment, media asset, prompt, embedding request, batch inference job, model checkpoint, fine-tuning job, cache entry, or agent step. |
| Contract | The compatibility and quality promise for a work unit. It tells URP what must be preserved and what may be changed. |
| Manifest | The durable record that maps a logical work unit to physical chunks, transforms, cache entries, model routes, summaries, lineage, checksums, and policy decisions. |
| Ledger | Append-only audit trail of every classification, policy decision, transform, cache hit, AI route, verification result, restore, deletion, and override. |
| Exact Bytes | Readback must return byte-for-byte identical content. This is the default for unknown or regulated data. |
| Exact Logical | Readback must return equivalent rows, records, messages, frames, or values, but physical layout can change. |
| Bounded Approximation | URP may reduce fidelity within explicitly measured error bounds. |
| Semantic | URP may preserve meaning instead of raw bytes, only when policy allows it. |
| Tombstone | Raw content was intentionally deleted or expired; lineage, deletion proof, and minimal metadata remain. |
| Rehydration | Reconstructing the logical view from manifest, chunks, transforms, cache records, or derived artifacts. |
| Reduction Proof | Metadata proving why a reduction is safe: checksums, sample entropy, transform identity, verifier output, policy id, and lineage. |
