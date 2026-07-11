# URP Worker

Local execution is implemented in `urp.executor`.

The worker service boundary is reserved for asynchronous reductions, lifecycle
jobs, lakehouse recommendations, training reducers, checkpoint reduction, and
plugin execution.

Run locally:

```bash
export URP_LOCAL_API_KEY="replace-with-a-random-local-secret"
urp service run --name worker --listen 127.0.0.1:8082
```

The local worker accepts inline `/v1/work-units/plan`,
`/v1/work-units/execute`, and `/v1/benchmarks/run`. Stored WorkUnit lifecycle
routes live on the control-plane service.
