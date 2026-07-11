# URP Live Examples

These examples exercise the local-ideal URP runtime without cloud credentials or external model providers.

Run:

```bash
PYTHONPATH=python python3 examples/live/run_live_examples.py --reset
```

The command creates `.urp-live-examples` and prints a JSON evidence report with:

- exact S3-compatible object ingest, manifest write, byte-range rehydration, and legal-hold delete denial;
- OpenAI-compatible chat completion with first-call cache miss and second-call exact cache hit;
- lakehouse mock adapter execution with rehydration and no external integration requirement;
- manifest explorer, savings, dashboard, and ledger-chain evidence from the same state directory.

The output intentionally includes generated IDs, byte counts, cache outcomes, verifier acceptance, redaction flags, and ledger counts so a reviewer can connect the use cases to runtime behavior.
