# URP Control Plane

Local-ideal control-plane entrypoint. The Python package exposes the concrete
control API through `urp.api.create_app()` when FastAPI is available, and a
dependency-free stdlib service through `urp.cli service run`.

Run locally:

```bash
export URP_LOCAL_API_KEY="replace-with-a-random-local-secret"
urp service run --name control-plane --listen 127.0.0.1:8080
```

`/healthz` and `/readyz` are public. All `/v1/*` routes and `/metrics` require
the key as a bearer token or `X-API-Key`.

Default local tests start the stdlib service on an ephemeral port and verify
`/healthz`, stored WorkUnit create/plan/execute, inline
`/v1/work-units/plan`, inline `/v1/work-units/execute`, persisted plan
create/list/get, manifest lookup,
manifest query, manifest explorer, redacted manifest export, manifest rehydrate/range rehydrate,
policy validate/evaluate, policy bundle publish/list/rollback/reload, plugin
register/list, local KMS key creation, backup/restore, exact cache
lookup/store, semantic cache policy gates, verifier-gated cache storage
rejection, savings and dashboard reports, production readiness, trace query,
structured log query, route feedback, auth checks, platform readiness, adapter conformance, and AI conformance. Ledger is
available through both batch query and a local `text/event-stream` endpoint at
`/v1/ledger/stream`. Platform profile and readiness routes are available at
`/v1/platforms`, `/v1/platforms/readiness`, and `/v1/platforms/matrix`.
