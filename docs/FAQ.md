# Frequently Asked Questions

## What is the Universal Reduction Plane?

Universal Reduction Plane (URP) is an open-source control and execution layer that
reduces unnecessary storage, transfer, and AI computation. It applies a common
WorkUnit, contract, policy, plan, verification, manifest, and ledger lifecycle to
data and AI workloads.

## What problem does URP solve?

URP solves fragmented optimization. Compression, deduplication, AI caching, context
reduction, model routing, lakehouse compaction, and training reduction normally use
different controls and evidence. URP gives them one safety and audit model.

## Is URP a universal compression algorithm?

No. Information theory prevents every possible input from being losslessly made
smaller. URP safely chooses among compression, dedupe, exact cache, context
reduction, routing, scheduling, or baseline passthrough according to the workload
contract.

## Does URP change application interfaces?

It is designed to minimize changes. URP exposes S3-style object operations,
OpenAI-compatible AI endpoints, POSIX paths, REST/OpenAPI, protobuf, CLI, and typed
SDKs.

## What is a WorkUnit?

A WorkUnit is URP's canonical input. It identifies the tenant, workload kind,
logical reference, payload or payload reference, namespace, contract request,
policy context, and trace. Objects, prompts, embeddings, table snapshots, stream
segments, training data, and checkpoints can all be WorkUnits.

## What does exact by default mean?

Unknown data receives an `exact_bytes` contract. URP must reconstruct the same byte
sequence and verify it before accepting the reduced representation.

## Can tenants share cached or deduplicated data?

Not by default. Cache keys, namespaces, chunks, stores, and direct reads are
tenant-scoped. Cross-tenant reuse is rejected to avoid privacy and authorization
leakage.

## How does URP verify an optimization?

The server runs a verifier against the actual candidate output. Exact byte paths
use restore checksums. AI and structured paths can require output shape, source
fingerprint, policy, and task-specific checks. A client Boolean is not accepted as
verification evidence.

## What happens when verification fails?

URP rejects the candidate output, records the failure, and invokes the plan's safe
baseline fallback. Failed reduced output is not served or cached.

## Does URP support OpenAI-compatible APIs?

Yes. The AI gateway exposes chat completions, text completions, embeddings, and
models. A deterministic mock provider is included. A credentialed
OpenAI-compatible HTTP adapter is opt-in.

## Does URP support S3?

The local gateway implements Put, Get, Head, list, delete, byte ranges, and verified
multipart operations. An AWS S3 SigV4 adapter is available when credentials are
configured. URP is not a complete replacement for every S3 extension.

## Can URP estimate cost savings?

Yes, through an explicit scenario model:

```bash
urp report impact --scenario examples/impact/illustrative-portfolio.json
```

The calculator separates assumptions from outputs and includes URP operating cost,
implementation cost, payback, and model boundaries.

## Does URP claim energy or carbon savings?

Not without measured telemetry. The impact model leaves energy unestimated until
the operator supplies energy per avoided model call. Carbon additionally requires
a location- and time-appropriate grid intensity.

## Is URP production ready?

URP is ready for local evaluation, integration testing, container build, Docker
Compose, and Kubernetes/Helm deployment in observe mode. Production scale, managed
stores, high availability, ingress/TLS, workload identity, capacity testing, and
compliance remain environment-specific responsibilities.

## Which deployment modes are available?

`observe` records decisions without serving reduced output. `shadow` executes and
verifies isolated candidate paths. `enforce` serves accepted optimized paths and
falls back when necessary.

## How is URP licensed?

The project is available under the Apache License 2.0, which permits commercial and
non-commercial use, modification, and distribution under the license terms.

## How should URP be cited?

Use the repository's `CITATION.cff`, identify the exact release tag or commit, and
cite the [URP technical paper](WHITE_PAPER.md) when discussing the architecture or
impact model.
