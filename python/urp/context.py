from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List

from .contracts import stable_json_hash


@dataclass(frozen=True)
class ContextChunk:
    text: str
    source_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        # Source location is lineage, not content identity. Including it would
        # make two identical context blocks at different positions non-dedupable.
        return stable_json_hash({"text": " ".join(self.text.split()), "role": self.metadata.get("role")})


@dataclass(frozen=True)
class CompiledContext:
    chunks: List[ContextChunk]
    tokens_before: int
    tokens_after: int
    removed_fingerprints: List[str]
    cache_prefix_preserved: bool = False
    lossy_truncation_applied: bool = False
    lossy_truncation_permitted: bool = False
    budget_truncation_skipped: bool = False
    prefix_exceeds_budget: bool = False
    prefix_chunk_count: int = 0

    def text(self) -> str:
        return "\n\n".join(chunk.text for chunk in self.chunks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tokens_before": self.tokens_before,
            "tokens_after": self.tokens_after,
            "removed_fingerprints": self.removed_fingerprints,
            "source_ids": [chunk.source_id for chunk in self.chunks],
            "cache_prefix_preserved": self.cache_prefix_preserved,
            "lossy_truncation_applied": self.lossy_truncation_applied,
            "lossy_truncation_permitted": self.lossy_truncation_permitted,
            "budget_truncation_skipped": self.budget_truncation_skipped,
            "prefix_exceeds_budget": self.prefix_exceeds_budget,
            "prefix_chunk_count": self.prefix_chunk_count,
        }


def approximate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4) if text else 0


def compile_context(
    chunks: Iterable[ContextChunk],
    max_tokens: int = 4000,
    *,
    preserve_cache_prefix: bool = True,
    allow_lossy_truncation: bool = False,
) -> CompiledContext:
    """Dedupe context and, only when opted in, drop suffix chunks over budget.

    When a chunk is marked as a cache breakpoint, every chunk up to and
    including that breakpoint is copied unchanged. Deduping or budget-dropping
    inside that prefix would edit the provider prompt-cache key. Trimming is
    allowed only after the breakpoint, and only when ``allow_lossy_truncation``
    is true. That flag is off by default because dropping messages is lossy.

    With no breakpoint, identical later chunks are still deduped. Budget
    drops still require the lossy opt-in.
    """
    material = list(chunks)
    if max_tokens < 0:
        raise ValueError("max_tokens must be non-negative")
    breakpoint = -1
    if preserve_cache_prefix:
        for index, chunk in enumerate(material):
            if chunk_is_cache_breakpoint(chunk):
                breakpoint = index
    prefix = material[: breakpoint + 1] if breakpoint >= 0 else []
    mutable = material[breakpoint + 1 :]

    kept: List[ContextChunk] = []
    removed: List[str] = []
    seen: set[str] = set()
    tokens_before = 0
    tokens_after = 0
    for chunk in prefix:
        chunk_tokens = approximate_tokens(chunk.text)
        tokens_before += chunk_tokens
        tokens_after += chunk_tokens
        kept.append(chunk)
        seen.add(chunk.fingerprint)
    prefix_tokens = tokens_after
    lossy_applied = False
    budget_skipped = False
    for chunk in mutable:
        chunk_tokens = approximate_tokens(chunk.text)
        tokens_before += chunk_tokens
        fingerprint = chunk.fingerprint
        if fingerprint in seen:
            removed.append(fingerprint)
            continue
        over_budget = tokens_after + chunk_tokens > max_tokens
        if over_budget and not allow_lossy_truncation:
            budget_skipped = True
            seen.add(fingerprint)
            kept.append(chunk)
            tokens_after += chunk_tokens
            continue
        if over_budget:
            removed.append(fingerprint)
            lossy_applied = True
            continue
        seen.add(fingerprint)
        kept.append(chunk)
        tokens_after += chunk_tokens
    return CompiledContext(
        kept,
        tokens_before,
        tokens_after,
        removed,
        cache_prefix_preserved=breakpoint >= 0,
        lossy_truncation_applied=lossy_applied,
        lossy_truncation_permitted=allow_lossy_truncation,
        budget_truncation_skipped=budget_skipped or prefix_tokens > max_tokens,
        prefix_exceeds_budget=prefix_tokens > max_tokens,
        prefix_chunk_count=len(prefix),
    )


def context_chunks_from_openai_messages(messages: list[dict[str, Any]]) -> List[ContextChunk]:
    chunks: List[ContextChunk] = []
    for idx, msg in enumerate(messages):
        content = _message_text(msg)
        if msg.get("role") in {"system", "developer", "tool"}:
            chunks.append(ContextChunk(content, f"message:{idx}", _message_metadata(msg)))
    return chunks


def compile_openai_messages(
    messages: list[dict[str, Any]],
    max_tokens: int = 4000,
    *,
    preserve_cache_prefix: bool = True,
    allow_lossy_truncation: bool = False,
) -> tuple[CompiledContext, list[dict[str, Any]]]:
    """Compile system, developer, and tool messages without editing a cached prefix.

    A breakpoint may sit on any role, including a user message that is not
    itself compiled. Every eligible message at or before that index stays.
    Budget truncation of later eligible messages runs only when
    ``allow_lossy_truncation`` is true.
    """
    breakpoint = -1
    if preserve_cache_prefix:
        for index, message in enumerate(messages):
            if message_is_cache_breakpoint(message):
                breakpoint = index
    chunks = context_chunks_from_openai_messages(messages)
    if breakpoint >= 0:
        frozen = 0
        for chunk in chunks:
            message_index = int(str(chunk.source_id).split(":", 1)[1])
            if message_index <= breakpoint:
                frozen += 1
        if frozen:
            last = chunks[frozen - 1]
            metadata = dict(last.metadata)
            metadata["cache_breakpoint"] = True
            chunks[frozen - 1] = ContextChunk(last.text, last.source_id, metadata)
    compiled = compile_context(
        chunks,
        max_tokens=max_tokens,
        preserve_cache_prefix=preserve_cache_prefix,
        allow_lossy_truncation=allow_lossy_truncation,
    )
    kept_source_ids = {chunk.source_id for chunk in compiled.chunks}
    result: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        role = message.get("role")
        if role in {"system", "developer", "tool"} and f"message:{index}" not in kept_source_ids:
            continue
        result.append(dict(message))
    return compiled, result


def message_is_cache_breakpoint(message: dict[str, Any]) -> bool:
    if message.get("cache_breakpoint") is True or message.get("urp_cache_breakpoint") is True:
        return True
    if _cache_control_marks_breakpoint(message.get("cache_control")):
        return True
    content = message.get("content")
    if isinstance(content, list):
        return any(isinstance(part, dict) and _cache_control_marks_breakpoint(part.get("cache_control")) for part in content)
    return False


def chunk_is_cache_breakpoint(chunk: ContextChunk) -> bool:
    if chunk.metadata.get("cache_breakpoint") is True or chunk.metadata.get("urp_cache_breakpoint") is True:
        return True
    return _cache_control_marks_breakpoint(chunk.metadata.get("cache_control"))


def _cache_control_marks_breakpoint(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("type"))


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    return str(content)


def _message_metadata(message: dict[str, Any]) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {"role": message.get("role")}
    if message.get("cache_breakpoint") is True:
        metadata["cache_breakpoint"] = True
    if message.get("urp_cache_breakpoint") is True:
        metadata["urp_cache_breakpoint"] = True
    if isinstance(message.get("cache_control"), dict):
        metadata["cache_control"] = dict(message["cache_control"])
    content = message.get("content")
    if isinstance(content, list) and any(isinstance(part, dict) and isinstance(part.get("cache_control"), dict) for part in content):
        metadata["cache_breakpoint"] = True
    return metadata
