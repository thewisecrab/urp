# URP S3 Gateway

Local-ideal S3 compatibility surface is implemented by `urp.adapters.LocalS3Adapter`.

The adapter supports Put/Get/Head, range-read, and multipart
create/part/complete/abort behavior against local chunks, manifests, and ledger
state. Full wire-compatible S3 service behavior remains a production adapter
backed by conformance tests.

Run the local JSON facade:

```bash
export URP_LOCAL_API_KEY="replace-with-a-random-local-secret"
urp service run --name gateway-s3 --listen 127.0.0.1:9000
```

The local facade exposes `/v1/s3/objects`, `/v1/s3/objects/head`,
`/v1/s3/objects/get`, `/v1/s3/objects/range`, `/v1/s3/multipart/create`,
`/v1/s3/multipart/part`, `/v1/s3/multipart/complete`, and
`/v1/s3/multipart/abort` for conformance and smoke testing without external
object storage.

GetObject and range responses are raw `application/octet-stream`. Every part
is digest-verified, multipart completion is state-gated, and all object routes
require the configured bearer token.
