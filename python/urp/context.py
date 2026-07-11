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

    def text(self) -> str:
        return "\n\n".join(chunk.text for chunk in self.chunks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tokens_before": self.tokens_before,
            "tokens_after": self.tokens_after,
            "removed_fingerprints": self.removed_fingerprints,
            "source_ids": [chunk.source_id for chunk in self.chunks],
        }


def approximate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4) if text else 0


def compile_context(chunks: Iterable[ContextChunk], max_tokens: int = 4000) -> CompiledContext:
    seen: set[str] = set()
    kept: List[ContextChunk] = []
    removed: List[str] = []
    tokens_before = 0
    tokens_after = 0
    for chunk in chunks:
        chunk_tokens = approximate_tokens(chunk.text)
        tokens_before += chunk_tokens
        fp = chunk.fingerprint
        if fp in seen:
            removed.append(fp)
            continue
        if tokens_after + chunk_tokens > max_tokens:
            removed.append(fp)
            continue
        seen.add(fp)
        kept.append(chunk)
        tokens_after += chunk_tokens
    return CompiledContext(kept, tokens_before, tokens_after, removed)


def context_chunks_from_openai_messages(messages: list[dict[str, Any]]) -> List[ContextChunk]:
    chunks: List[ContextChunk] = []
    for idx, msg in enumerate(messages):
        content = str(msg.get("content", ""))
        if msg.get("role") in {"system", "developer", "tool"}:
            chunks.append(ContextChunk(content, f"message:{idx}", {"role": msg.get("role")}))
    return chunks


def compile_openai_messages(messages: list[dict[str, Any]], max_tokens: int = 4000) -> tuple[CompiledContext, list[dict[str, Any]]]:
    compiled = compile_context(context_chunks_from_openai_messages(messages), max_tokens=max_tokens)
    kept_source_ids = {chunk.source_id for chunk in compiled.chunks}
    result: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        role = message.get("role")
        if role in {"system", "developer", "tool"} and f"message:{index}" not in kept_source_ids:
            continue
        result.append(dict(message))
    return compiled, result
