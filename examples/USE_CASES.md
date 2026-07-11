# URP Local Use Cases

These use cases are backed by `examples/live/run_live_examples.py`. They are written as product-facing scenarios, but each one points to a concrete runtime field that the live example emits.

## 1. Exact Object Storage Reduction

Platform teams can place URP in front of S3-compatible object traffic to store exact-byte objects, record manifests, and allow byte-range rehydration.

Evidence from the live runner:

- `object_gateway_exact.rehydrated_exact` proves byte-for-byte restore.
- `object_gateway_exact.range_preview` proves range-read behavior.
- `object_gateway_exact.head.metadata` and `head.tags` show metadata and tags survive ingestion.
- `object_gateway_exact.delete_guardrail.reason` shows legal hold blocks deletion.

## 2. AI Gateway Exact Cache

AI platform teams can run URP as an OpenAI-compatible gateway that preserves prompts out of raw logs, routes the request, writes a compute manifest, and uses exact cache hits when source fingerprints match.

Evidence from the live runner:

- `ai_gateway_exact_cache.first_cache` is `miss`.
- `ai_gateway_exact_cache.second_cache` is `exact_hit`.
- `ai_gateway_exact_cache.provider_avoided_on_second_call` is `true`.
- `ai_gateway_exact_cache.raw_prompt_logged` is `false`.
- `ai_gateway_exact_cache.compute_manifest.accepted_by_verifier` is `true`.

## 3. Lakehouse Adapter Contract

Data engineering teams can represent table snapshots and structured files as WorkUnits before wiring live Iceberg, Delta, Hudi, or warehouse adapters.

Evidence from the live runner:

- `lakehouse_mock_adapter.accepted` proves the adapter can execute a WorkUnit locally.
- `lakehouse_mock_adapter.contract` records the exact logical contract.
- `lakehouse_mock_adapter.external_integrations_required` is `false`.
- `lakehouse_mock_adapter.rehydrated_contains_snapshot_id` proves the local payload was preserved and can be rehydrated.

## 4. Audit And Executive Reporting

Security, platform, and finance stakeholders need a common evidence stream. URP uses manifests, ledger events, structured logs, metrics, and reports from the same lifecycle.

Evidence from the live runner:

- `summary.ledger_chain_valid` proves JSONL ledger hash chaining.
- `reports_and_audit.manifest_explorer.count` proves the manifests are discoverable.
- `reports_and_audit.savings` shows local savings metrics.
- `reports_and_audit.dashboard_sections` confirms executive, platform, AI, data, and security dashboard sections are present.

## 5. Local-Ideal Adoption Path

The local runner demonstrates the default adoption posture:

- no external services are required;
- unknown object data remains exact by default;
- semantic or lossy paths are not enabled silently;
- deletion is guarded by policy and legal-hold metadata;
- every path emits inspectable runtime evidence.
