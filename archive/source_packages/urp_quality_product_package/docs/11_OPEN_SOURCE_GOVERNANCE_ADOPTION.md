# 11 — Open Source Governance and Adoption

## Purpose

URP should be open source to maximize trust, adoption, auditability, and platform compatibility. The open-source strategy must be designed from the beginning rather than added later.

## License recommendation

Use Apache-2.0 for the core project.

Reasons:

- enterprise-friendly;
- patent grant;
- widely understood;
- compatible with commercial offerings;
- encourages broad adoption.

## Governance goals

- prevent single-vendor lock-in;
- keep manifest and policy specs open;
- maintain conformance suites publicly;
- support commercial ecosystems without weakening the commons;
- make security and compatibility decisions transparent.

## Project structure

Recommended top-level repositories:

### urp

Core monorepo.

### urp-conformance

Protocol and plugin conformance tests. Can be inside monorepo initially.

### urp-plugins

Community plugin registry.

### urp-spec

If URP becomes widely adopted, split manifest/policy/protocol specs into a standards repo.

## Maintainer roles

### Core maintainer

Can merge core changes, release versions, and approve plugin API changes.

### Area maintainer

Owns an area such as S3 gateway, AI gateway, policy, security, SDK, docs, or conformance.

### Security maintainer

Handles private vulnerability reports and coordinated disclosure.

### Plugin maintainer

Owns a plugin but not core.

### Reviewer

Can approve changes but not release.

## Decision process

Use:

- public RFCs for major changes;
- maintainer approval for routine changes;
- security private process for vulnerabilities;
- compatibility review for manifest/policy changes.

## RFC template

```markdown
# RFC: Title

## Summary
## Problem
## Goals
## Non-goals
## User impact
## Technical design
## Manifest changes
## Policy changes
## Security impact
## Compatibility impact
## Alternatives
## Rollout
## Open questions
```

## Compatibility policy

Stable specs:

- manifest schema;
- work unit schema;
- policy schema;
- ledger event schema;
- plugin descriptor;
- conformance tests.

Breaking changes require:

- RFC;
- migration tool;
- version bump;
- deprecation window;
- compatibility tests.

## Conformance certification

A plugin or adapter can claim conformance only when it passes public tests.

Conformance levels:

- experimental;
- alpha;
- beta;
- stable;
- certified.

Certified may require human review or third-party validation.

## Open-source core boundaries

The open-source core must include enough to be useful:

- policy engine;
- manifest store;
- ledger;
- S3 gateway baseline;
- AI gateway baseline;
- chunking;
- compression plugin interface;
- exact cache;
- basic semantic cache with guardrails;
- CLI;
- SDKs;
- conformance tests.

Do not put the entire useful product behind a proprietary wall.

## Commercial ecosystem

Healthy commercial offerings can include:

- managed URP cloud;
- enterprise dashboards;
- hosted policy workflows;
- compliance templates;
- certified connectors;
- support;
- managed semantic indexes;
- optimization recommendations.

Avoid proprietary-only manifest formats or plugins required for basic functionality.

## Community adoption tactics

### Developers

- simple Docker quickstart;
- CLI demos;
- OpenAI-compatible proxy demo;
- S3 local gateway demo;
- clear SDK examples.

### Startups

- cost-saving templates;
- Vercel/Fly/Render/Railway examples;
- local object store examples;
- small team policy defaults.

### Enterprises

- reference architectures;
- threat model;
- compliance guide;
- migration playbooks;
- conformance reports;
- policy-as-code integration;
- Helm chart.

### Researchers

- benchmark harness;
- reproducible workloads;
- paper implementation notes;
- plugin API for new algorithms.

### Cloud providers

- backend adapters;
- marketplace packages;
- compatibility docs;
- no lock-in stance.

## Documentation standards

Each feature doc must include:

- purpose;
- user story;
- configuration;
- API;
- manifest fields;
- policy fields;
- metrics;
- security considerations;
- tests;
- rollback.

## Release process

Recommended release train:

- monthly minor releases;
- patch releases as needed;
- LTS every six months once mature;
- security releases immediately.

Release checklist:

- all tests pass;
- conformance pass;
- schema compatibility check;
- docs updated;
- changelog;
- migration notes;
- signed artifacts;
- SBOM;
- vulnerability scan.

## Security process

- SECURITY.md with contact;
- private vulnerability intake;
- severity scoring;
- embargo process;
- patch releases;
- advisory publication;
- credit reporters.

## Supply-chain security

Use:

- signed commits for maintainers where possible;
- signed releases;
- SBOM;
- dependency scanning;
- SLSA-oriented build process;
- reproducible builds for critical binaries;
- container image scanning.

## Trademark

If URP becomes large, define trademark rules:

- allow "compatible with URP" only with conformance tests;
- prevent misleading "certified" claims;
- keep community forks healthy.

## Project values

- compatibility;
- transparency;
- reversibility;
- safety;
- measurable savings;
- open specs;
- pragmatic engineering.

## Community anti-patterns

Avoid:

- hype claims;
- closed governance;
- cloud-provider favoritism;
- proprietary extensions that break portability;
- unreviewed plugins advertised as safe;
- docs that hide limitations.

## Good first issues

- improve CLI examples;
- add manifest sample;
- add policy validation tests;
- build a small adapter;
- add dashboard screenshots;
- write a benchmark workload;
- improve SDK docs.

## Advanced contributor areas

- S3 conformance;
- semantic cache verifier;
- lakehouse transaction integration;
- KV-cache telemetry;
- training reducer;
- plugin sandbox;
- policy proof engine;
- energy scheduler.

## Adoption message

URP should be introduced as:

> A compatibility-first open-source reduction layer for data and AI workloads, designed to reduce infrastructure waste without forcing rewrites or hiding risk.

## Long-term standardization

If widely adopted, URP can become an open standard for:

- reduction manifests;
- compute manifests;
- semantic cache safety metadata;
- AI route manifests;
- reduction proofs;
- policy-gated lifecycle transformations.

## Governance invariant

The open-source project must preserve user trust by making reduction decisions inspectable and portable.
