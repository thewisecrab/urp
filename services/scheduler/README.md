# URP Scheduler

Scheduler v0 is implemented in `urp.scheduler`.

It supports local deadline/carbon-signal decisions and provides the contract for
future production queue and placement adapters.

Run locally:

```bash
export URP_LOCAL_API_KEY="replace-with-a-random-local-secret"
urp service run --name scheduler --listen 127.0.0.1:8083
```

The local scheduler exposes `/v1/scheduler/submit` and `/v1/scheduler/jobs` and
persists decisions in the selected URP state directory.
