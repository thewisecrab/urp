# Codex Build Prompt

You are building Universal Reduction Plane (URP), a single open-source product that reduces data and AI infrastructure waste through one lifecycle:

```text
Work Unit + Contract + Policy -> Plan -> Execute -> Verify -> Manifest + Ledger
```

Do not split the product into separate data and AI products. Internal modules may be separated, but the external model must be one URP.

## Build goals

1. Implement the core domain model.
2. Implement policy evaluation with safe defaults.
3. Implement a planner that handles byte objects and AI prompt requests.
4. Implement exact-safe data execution.
5. Implement an OpenAI-compatible AI gateway skeleton.
6. Implement manifests, ledger, CLI, metrics, and tests.
7. Keep all semantic/approximate reducers policy-gated and disabled by default.

## Hard invariants

- Unknown data defaults to exact preservation.
- Cross-tenant cache and dedupe are disabled by default.
- Semantic reduction requires policy approval and verifier.
- Every executed action writes ledger events.
- Every stored or computed result gets a manifest.
- Exact-byte contracts must support byte-for-byte rehydration.
- Plugin interfaces must be versioned and conformance-tested.
- Rollback paths must exist before advanced reducers are enabled.

## First issue sequence

1. Make tests pass.
2. Convert reference skeleton into packages.
3. Add schema validation.
4. Add local manifest store.
5. Add JSONL ledger.
6. Add CLI commands.
7. Add object exact path.
8. Add AI exact cache.
9. Add context compiler.
10. Add API skeleton.

## Definition of done

A demo should show:

```bash
urp plan --kind byte_object --input ./sample.log
urp execute --kind byte_object --input ./sample.log
urp manifest get <id>
urp gateway ai --provider mock
curl /v1/chat/completions twice and see second request served from exact cache
```

All output must include work_unit_id and manifest_id where applicable.
