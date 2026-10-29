"""Copy provider-reported prompt-cache usage into ledger and trace fields.

Recognized response fields:

- OpenAI: ``usage.prompt_tokens``, ``usage.completion_tokens``, and
  ``usage.prompt_tokens_details.cached_tokens`` (also
  ``usage.input_tokens_details.cached_tokens``).
- Anthropic: ``usage.input_tokens``, ``usage.output_tokens``,
  ``usage.cache_read_input_tokens``, and ``usage.cache_creation_input_tokens``.

OpenTelemetry GenAI names, aligned with the development semantic conventions
for inference usage (cache tokens are included in ``gen_ai.usage.input_tokens``;
Anthropic reports them separately, so those counts are added only when the
Anthropic fields are present and the OpenAI prompt total is not):

- ``gen_ai.usage.input_tokens``
- ``gen_ai.usage.output_tokens``
- ``gen_ai.usage.cache_read.input_tokens``
- ``gen_ai.usage.cache_creation.input_tokens``

Missing fields are omitted. Conflicting fields are kept raw and not collapsed.
Nothing is inferred from token text.
"""

from __future__ import annotations

from typing import Any, Mapping


def extract_provider_cache_usage(response: Mapping[str, Any] | None) -> dict[str, Any]:
    usage = response.get("usage") if isinstance(response, Mapping) else None
    if not isinstance(usage, Mapping):
        return _empty()

    prompt_tokens = _non_negative_int(usage.get("prompt_tokens"))
    completion_tokens = _non_negative_int(usage.get("completion_tokens"))
    input_tokens = _non_negative_int(usage.get("input_tokens"))
    output_tokens = _non_negative_int(usage.get("output_tokens"))
    cached_tokens = _cached_tokens(usage)
    cache_read = _non_negative_int(usage.get("cache_read_input_tokens"))
    cache_creation = _non_negative_int(usage.get("cache_creation_input_tokens"))

    provider_usage: dict[str, int] = {}
    if prompt_tokens is not None:
        provider_usage["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        provider_usage["completion_tokens"] = completion_tokens
    if input_tokens is not None:
        provider_usage["input_tokens"] = input_tokens
    if output_tokens is not None:
        provider_usage["output_tokens"] = output_tokens
    if cached_tokens is not None:
        provider_usage["prompt_tokens_details.cached_tokens"] = cached_tokens
    if cache_read is not None:
        provider_usage["cache_read_input_tokens"] = cache_read
    if cache_creation is not None:
        provider_usage["cache_creation_input_tokens"] = cache_creation

    conflicts: list[str] = []
    gen_ai: dict[str, int] = {}

    if cached_tokens is not None and cache_read is not None and cached_tokens != cache_read:
        conflicts.append("cache_read")
    elif cached_tokens is not None:
        gen_ai["gen_ai.usage.cache_read.input_tokens"] = cached_tokens
    elif cache_read is not None:
        gen_ai["gen_ai.usage.cache_read.input_tokens"] = cache_read
    if cache_creation is not None:
        gen_ai["gen_ai.usage.cache_creation.input_tokens"] = cache_creation

    if completion_tokens is not None and output_tokens is not None and completion_tokens != output_tokens:
        conflicts.append("output_tokens")
    elif completion_tokens is not None:
        gen_ai["gen_ai.usage.output_tokens"] = completion_tokens
    elif output_tokens is not None:
        gen_ai["gen_ai.usage.output_tokens"] = output_tokens

    anthropic_cache_present = cache_read is not None or cache_creation is not None
    anthropic_added = False
    if prompt_tokens is not None and input_tokens is not None and prompt_tokens != input_tokens:
        conflicts.append("input_tokens")
    elif prompt_tokens is not None and anthropic_cache_present:
        conflicts.append("input_tokens")
    elif prompt_tokens is not None:
        gen_ai["gen_ai.usage.input_tokens"] = prompt_tokens
    elif input_tokens is not None and anthropic_cache_present:
        gen_ai["gen_ai.usage.input_tokens"] = input_tokens + (cache_read or 0) + (cache_creation or 0)
        anthropic_added = True
    elif input_tokens is not None:
        gen_ai["gen_ai.usage.input_tokens"] = input_tokens

    cache_fields_present = any(value is not None for value in (cached_tokens, cache_read, cache_creation))
    return {
        "present": bool(provider_usage),
        "cache_fields_present": cache_fields_present,
        "inferred": False,
        "provider_usage": provider_usage,
        "gen_ai_usage": gen_ai,
        "conflicts": conflicts,
        "anthropic_cache_added_to_input_tokens": anthropic_added,
    }


def _empty() -> dict[str, Any]:
    return {
        "present": False,
        "cache_fields_present": False,
        "inferred": False,
        "provider_usage": {},
        "gen_ai_usage": {},
        "conflicts": [],
        "anthropic_cache_added_to_input_tokens": False,
    }


def _cached_tokens(usage: Mapping[str, Any]) -> int | None:
    for key in ("prompt_tokens_details", "input_tokens_details"):
        details = usage.get(key)
        if isinstance(details, Mapping) and "cached_tokens" in details:
            return _non_negative_int(details.get("cached_tokens"))
    return None


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value
