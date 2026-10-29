# Revision notes (v1.1-draft)

**Date:** 2026-10-29  
**Status:** draft revision of technical report v1.0. The published PDF (`docs/assets/URP-White-Paper-v1.0.pdf`) is unchanged and was not regenerated.  
**Software:** still 0.1.0. This note does not bump the version.

v1.0 text remains in git history at `f3fc148`. The edits in `docs/WHITE_PAPER.md` correct overclaims and add this draft. They do not replace the v1.0 scenario arithmetic ($7,798.56 gross, $5,298.56 after the supplied operating cost, 5.66 month payback).

## What the code on this branch actually changes

- `python/urp/impact.py` still prices omitted cache fields with the historical full input list rate, and the result flags that path (`input_pricing.mode = list_price`, `cache_discount_applied = false`, `backward_compatible_list_price = true`). That path can overstate savings when a provider would have billed prompt-cache reads below list price.
- Operators can set `input_pricing` to `effective_blended` with `provider_cache_read_share`, `cache_read_price_ratio` (example shape: 0.1 for a read billed at 0.1× the base input rate), and, together, `provider_cache_write_share` plus `cache_write_premium` (example shapes: 1.25 and 2). Avoided calls and context-compiler input tokens then use that blended rate. The blend is operator-supplied. It does not model extra writes from editing a cached prefix.
- Avoided cost, kWh, and CO2e are labelled gross, attributional, and at constant demand (`rebound_adjusted: false`). Existing keys such as `monthly_ai_cost_avoided` and `monthly_kwh_avoided` remain. `gross_*_avoided` aliases carry the same numbers. `net_monthly_savings` still means gross avoided direct cost minus the supplied URP operating cost. It is not rebound-adjusted.
- `rebound_indicator(actual_absolute_reduction, expected_gross_reduction)` computes `R = 1 - (actual_absolute_reduction / expected_gross_reduction)` from caller-supplied totals. It does not observe a deployment.
- Energy stays unestimated unless the operator supplies either `energy_kwh_per_avoided_model_call` or both `energy_kwh_fixed_per_avoided_call` and `energy_kwh_per_token` (`E = E_fixed * avoided calls + E_token * avoided tokens`). Neither term is defaulted to zero or to a literature value. Context-only reductions include token energy and not the fixed per-call term.
- The AI gateway copies provider cache fields when a response already contains them: OpenAI `usage.prompt_tokens_details.cached_tokens` (or `input_tokens_details.cached_tokens`) and Anthropic `cache_read_input_tokens` / `cache_creation_input_tokens`. Ledger event `ai.provider_usage.recorded` and span `urp.ai.usage` use `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cache_read.input_tokens`, and `gen_ai.usage.cache_creation.input_tokens` when the mapping is unambiguous. Missing fields are omitted. Conflicting fields are kept raw. Mock usage without those cache fields is not recorded as provider cache usage. For Anthropic, cache read and cache creation counts are added into `gen_ai.usage.input_tokens` only when the separate Anthropic input count is present and an OpenAI prompt total is not; the flag `anthropic_cache_added_to_input_tokens` records that addition.
- The context compiler keeps a declared cache breakpoint prefix unchanged (message `cache_breakpoint`, `urp_cache_breakpoint`, or Anthropic-style `cache_control.type`, including on a content part or a later user message). Deduping and budget drops apply only after that prefix. Budget drops stay off unless the request sets `allow_lossy_context_truncation` and policy allows `context_budget_truncate`. That action is denied unless a policy rule explicitly allows it.
- `KeywordModelRouter` and `LexicalJaccardScorer` remain the defaults. `DecisionBackend` is a local protocol for a later calibrated router, scorer, and verifier. No vendor client, key, or network call was added. The default semantic-cache threshold is still the fixed 0.82 lexical cutoff.
- Hypothesis tests check `restore(put(x))[start:end] == x[start:end]` for fixed chunks, content-defined chunks, zlib/zstd-or-fallback compression, and multipart upload. `tests/fixtures/restore_corpus` is a frozen 0.1.0 manifest fixture (zlib fallback; not a benchmark).

## New limitation

Savings figures are attributional and exclude rebound. A gross avoided-cost or avoided-kWh total at constant demand is not a reduction in the organization's total spend or energy if usage grows.

## Draft research and engineering agenda

These items are not implemented on this branch.

- Rebound measurement via an observe-mode baseline plus staggered enforcement, comparing absolute before/after totals with the gross attributional estimate (`R` above). The helper does not perform that measurement.
- Cache-aware cost as an operator-supplied effective rate, now calculated when requested, still not filled from a live provider invoice.
- Witnessed ledger checkpoints.
- A pluggable calibrated router and verifier backend. The interface is local only.

## Related work added in this draft

Citations below are the references requested for this draft. Descriptions in parentheses are scope notes, not measurements of URP.

- Luccioni et al., arXiv:2501.16548 (rebound, FAccT 2025).
- Lumer et al., arXiv:2601.06007 (provider prompt caching).
- Fu et al., arXiv:2610.28577 (cache engineering for agents).
- Nguyen et al., CliffCompaction, arXiv:2609.26779.
- Schroeder et al., vCache, arXiv:2502.03771 (ICLR 2026). A static semantic-cache threshold has no error guarantee. This is relevant to `python/urp/semantic_cache.py`, whose default threshold is a fixed 0.82 on a lexical Jaccard/trigram blend.
- Singh et al., Krites, arXiv:2602.13165.
- Hou and Yang, Control Under Compression, arXiv:2608.01056.
- Gu et al., arXiv:2502.07776 (prompt-cache timing side channels, ICML 2025). Preserving a prefix so a provider cache key does not change is not a defense against timing side channels.
- Zhang et al., arXiv:2609.35908 (semantic cache poisoning).
- Chung et al., ML.ENERGY, arXiv:2505.06371.
- Vellaisamy et al., arXiv:2608.28044 (request energy versus token energy). This is why the impact model can take a fixed per-call term and a per-token term, both operator-supplied.
- Guan, AEX, arXiv:2603.14283, and Wang and Tian, arXiv:2606.22560 (signed gateway and transform receipts).
- Ghosh, Tracekit, arXiv:2609.35659 (witnessed transparency logs).
- LLMLingua-2, arXiv:2403.12968.
- WildChat, arXiv:2405.01470.
- LMSYS-Chat-1M, arXiv:2309.11998.
- ServeGen, arXiv:2505.09999.
- Deußer et al., arXiv:2609.37647, and Sun et al., arXiv:2609.26758 (TypeSafe Jev decision model: calibrated, with option-name bias). URP's router is still the keyword scorer; it is not that model.

## IEA figure

Checked on 2026-10-29:

- The cited 2025 IEA *Energy and AI* page still describes a base case of about 945 TWh of data-centre electricity in 2030 (https://www.iea.org/reports/energy-and-ai/energy-demand-from-ai). The v1.0 arithmetic uses that figure and is unchanged.
- A later IEA executive summary, *Key Questions on Energy and AI*, describes electricity consumption from data centres roughly doubling from 485 TWh in 2025 to about 950 TWh in 2030 (https://www.iea.org/reports/key-questions-on-energy-and-ai/executive-summary).

TODO: do not swap the v1.0 worked example to 950 TWh, or to any URP share of it, without a new dated scenario. The 0.01–1% scale lens is gross avoided-work equivalents, not a net claim.

## Counts and the PDF

The 2026-07-11 receipt in `TEST_RESULTS.md` records 86 passing Python tests and a 14-page PDF. v1.0 prose that said 87 tests was inconsistent with that receipt. The receipt text is unchanged. The committed PDF `docs/assets/URP-White-Paper-v1.0.pdf` currently has 16 page objects (`/Type /Page` not followed by `s`). This draft did not re-render it. A separate 2026-10-29 section in `TEST_RESULTS.md` records 115 passed and 75.47% statement coverage under CPython 3.12.3.
