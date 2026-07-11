# URP AI Gateway

OpenAI-compatible local gateway.

Run the dependency-free mock server:

```bash
export URP_LOCAL_API_KEY="replace-with-a-random-local-secret"
urp gateway ai --provider mock --serve --listen 127.0.0.1:8080
```

Equivalent service runtime:

```bash
urp service run --name gateway-ai --listen 127.0.0.1:8081
```

Supported local endpoints:

- `POST /v1/chat/completions`
- `POST /v1/completions`
- `POST /v1/embeddings`
- `GET /v1/models`
- `GET /healthz`

OpenAI-compatible routes require the configured bearer token. Streaming is
rejected explicitly in the local-ideal runtime rather than silently buffered.
