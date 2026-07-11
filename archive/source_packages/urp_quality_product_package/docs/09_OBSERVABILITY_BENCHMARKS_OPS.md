# 09 — Observability, Benchmarks, SLOs, and Operations

## Purpose

URP must prove it saves resources without hiding risk. Observability is a product feature, not an afterthought.

## Measurement categories

URP should measure:

- bytes received;
- bytes physically stored;
- bytes avoided by dedupe;
- bytes avoided by compression;
- bytes avoided by lifecycle;
- tokens received;
- tokens removed by context compiler;
- tokens avoided by cache;
- model calls avoided;
- large-model calls avoided;
- GPU seconds avoided;
- training runs avoided;
- checkpoint bytes avoided;
- rehydration latency;
- gateway overhead;
- verifier failures;
- policy denials;
- cache staleness;
- fallback rate;
- plugin error rate;
- scheduler shifts.

## North-star metrics

### Verified useful output per joule

This is the long-term target. It is hard to measure perfectly but aligns URP with data-center reduction.

### Verified useful output per dollar

Useful for startups and enterprises.

### Verified useful output per byte

Useful for data platforms.

## Metric naming

Suggested Prometheus metrics:

```text
urp_work_units_total
urp_work_unit_bytes_in_total
urp_work_unit_bytes_stored_total
urp_bytes_avoided_total
urp_chunks_total
urp_chunk_dedupe_hits_total
urp_compression_ratio
urp_rehydration_seconds
urp_policy_denials_total
urp_verifier_failures_total
urp_cache_hits_total
urp_cache_misses_total
urp_ai_input_tokens_total
urp_ai_context_tokens_removed_total
urp_ai_large_model_calls_total
urp_ai_large_model_calls_avoided_total
urp_ai_fallbacks_total
urp_training_gpu_seconds_avoided_total
urp_scheduler_jobs_shifted_total
urp_manifest_write_seconds
urp_ledger_events_total
```

## Trace model

A request trace should include spans:

```text
urp.intake
urp.classify
urp.policy.evaluate
urp.plan
urp.execute
urp.transform
urp.cache.lookup
urp.ai.context_compile
urp.ai.route
urp.verify
urp.manifest.write
urp.ledger.append
urp.rehydrate
```

Span attributes:

- work_unit_id;
- manifest_id;
- tenant hash;
- namespace;
- contract;
- policy_bundle_id;
- mode;
- adapter;
- action;
- cache_result;
- model_route;
- verifier_result.

Do not put raw prompts or sensitive object keys in spans by default.

## Logs

Structured logs should include:

- severity;
- event type;
- work unit id;
- manifest id;
- policy bundle id;
- trace id;
- error code;
- redacted message.

Use logs for debugging, not audit. Ledger is audit.

## Dashboards

### Executive dashboard

- total bytes avoided;
- total AI calls avoided;
- total estimated cost avoided;
- peak compute shifted;
- risk events;
- savings by business unit.

### Platform dashboard

- gateway latency;
- manifest store health;
- chunk store health;
- ledger append rate;
- policy evaluation latency;
- plugin errors;
- fallback rate.

### AI dashboard

- requests by route;
- cache hit rates;
- semantic cache acceptance;
- context tokens removed;
- verifier failures;
- model escalation rates;
- p95 latency by path.

### Data dashboard

- storage by contract;
- hot/warm/cold distribution;
- dedupe domains;
- compression ratios;
- rehydration test status;
- lifecycle candidates.

### Security dashboard

- policy denials;
- semantic reductions;
- legal holds;
- cross-tenant attempts blocked;
- plugin changes;
- high-risk overrides.

## SLOs

### Gateway availability

Target:

- 99.9% for dev/small deployments;
- 99.99% for enterprise hot path.

### Exact rehydration correctness

Target:

- 100% for exact-byte contracts.

Any failure is severe.

### Policy evaluation latency

Target:

- p95 under 10 ms from warm cache for hot path.

### Manifest write latency

Target:

- p95 under 50 ms for local/regional metadata path.

### AI gateway overhead

Target:

- p95 overhead under 100 ms for cache miss pass-through;
- cache hit faster than baseline provider call.

### Cache correctness

Target:

- 0 known cross-tenant unauthorized hits.

### Verifier failure handling

Target:

- 100% fallback for required verifier failures.

## Error budgets

Optimization should consume error budget only explicitly.

If URP increases latency or failure rate beyond SLO:

- disable advanced reducers;
- keep exact path;
- keep observe mode;
- alert maintainers.

## Benchmark suites

### Object exact suite

Workloads:

- random bytes;
- repeated bytes;
- log-like text;
- shifted backups;
- JSON files;
- compressed files;
- encrypted-like random files;
- multipart uploads;
- range reads.

Metrics:

- write throughput;
- read throughput;
- stored bytes;
- metadata overhead;
- rehydration correctness.

### AI gateway suite

Workloads:

- repeated exact prompts;
- paraphrased prompts;
- long duplicated RAG context;
- tool-solvable questions;
- easy classification;
- hard reasoning;
- stale source cache;
- cross-tenant cache attempt.

Metrics:

- cache hit rate;
- false acceptance rate;
- large-model calls avoided;
- tokens avoided;
- latency;
- verifier failure rate.

### Lakehouse suite

Workloads:

- many small files;
- skewed partitions;
- duplicate row groups;
- low-cardinality columns;
- high-cardinality columns.

Metrics:

- storage reduction;
- query scan reduction;
- compaction time;
- snapshot correctness.

### Stream suite

Workloads:

- heartbeat events;
- duplicate messages;
- incident bursts;
- late arrivals;
- schema evolution.

Metrics:

- bytes reduced;
- replay correctness;
- anomaly preservation;
- consumer latency.

### Training suite

Workloads:

- duplicate dataset samples;
- repeated fine-tunes;
- checkpoints;
- adapters;
- failed experiments.

Metrics:

- training examples removed;
- GPU hours avoided;
- checkpoint bytes avoided;
- eval score preservation.

## Savings estimation

Savings should be separated into measured and estimated.

Measured:

- physical bytes stored;
- baseline bytes in;
- cache hit provider call avoided;
- tokens removed from prompt;
- chunks reused.

Estimated:

- joules avoided;
- cost avoided;
- future data-center capacity avoided.

Label estimates clearly.

## Rehydration testing

URP should periodically test restore paths.

Types:

- sampled exact-byte restore;
- full restore for selected critical datasets;
- table logical verification;
- AI cache source validation;
- manifest migration restore.

## Canarying

Rollout pattern:

1. observe only;
2. shadow transform;
3. canary exact mode;
4. expand exact mode;
5. canary semantic mode;
6. expand with SLO guardrails.

Canary inputs:

- tenant;
- namespace;
- percentage;
- work unit kind;
- contract.

## Rollback

Rollback strategies:

- bypass gateway;
- disable plugin;
- switch policy bundle;
- force exact contract;
- rehydrate from original chunks;
- clear semantic cache;
- disable model router;
- route to baseline model provider.

Every advanced feature needs a rollback path documented before production.

## Operations runbook

### Gateway degraded

1. check health endpoint;
2. check backend storage;
3. check manifest store;
4. check policy cache;
5. disable advanced reducers;
6. switch to pass-through if allowed;
7. alert owning team.

### Rehydration failure

1. mark manifest quarantined;
2. block lifecycle deletion for sources;
3. fetch chunks;
4. verify checksums;
5. inspect transform stack;
6. attempt fallback source;
7. emit incident ledger event;
8. run related manifest checks.

### Semantic cache incident

1. disable semantic cache for affected domain;
2. query ledger for accepted hits;
3. invalidate entries with affected source fingerprints;
4. notify application owners;
5. tighten thresholds/verifiers;
6. add regression tests.

### Policy misconfiguration

1. freeze current policy bundle;
2. roll back to previous bundle;
3. query ledger for affected decisions;
4. re-evaluate impacted work units;
5. publish postmortem.

### Plugin failure

1. disable plugin;
2. route to fallback;
3. quarantine manifests produced by plugin if needed;
4. run plugin conformance tests;
5. require signed update.

## Alerting

Critical alerts:

- exact rehydration failure;
- cross-tenant cache attempt accepted;
- policy evaluation unavailable in enforce mode;
- manifest store write failure;
- ledger append failure;
- verifier failure without fallback;
- legal hold deletion attempt;
- plugin signature failure.

Warning alerts:

- cache hit rate drops;
- compression ratio unexpectedly drops;
- p95 latency increases;
- dedupe index growth high;
- semantic cache staleness high;
- model fallback rate high;
- scheduler misses deadlines.

## Capacity planning

URP itself consumes resources.

Plan for:

- gateway CPU;
- chunking CPU;
- compression CPU;
- manifest database IOPS;
- ledger storage;
- cache RAM;
- semantic index storage;
- rehydration bandwidth;
- verifier compute.

URP must report its own overhead separately from savings.

## Cost accounting

Cost reports should break down:

- baseline cost;
- URP overhead;
- net savings;
- storage savings;
- AI inference savings;
- training savings;
- network savings;
- operational cost.

## Data quality

Reduction can expose data-quality problems:

- duplicate datasets;
- stale documents;
- unused logs;
- bloated prompts;
- repeated training samples;
- unused model variants.

URP should report these as recommendations.

## Benchmark acceptance for release

A release should not ship if:

- exact restore tests fail;
- policy tests fail;
- cache isolation tests fail;
- p95 hot-path overhead regresses beyond threshold;
- manifest migration breaks old samples;
- conformance suite fails.

## Ideal-state operations

In the ideal state, URP is operated like identity or observability infrastructure: always on, conservative by default, measured continuously, and rolled out through policy.
