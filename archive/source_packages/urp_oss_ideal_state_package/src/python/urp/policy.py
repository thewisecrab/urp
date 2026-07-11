from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class PolicyRule:
    name: str
    match: dict[str, Any]
    contract: str = "exact-byte"
    allowed_transforms: list[str] = field(default_factory=lambda: ["whole-object-dedupe", "content-defined-chunking", "zstd"])
    forbidden_transforms: list[str] = field(default_factory=list)
    dedupe_domain: str = "tenant"
    requires_approval: bool = False

@dataclass
class ReductionPolicy:
    policy_version: str = "v1"
    rules: list[PolicyRule] = field(default_factory=list)

    def match_rule(self, resource_type: str, attrs: dict[str, Any] | None = None) -> PolicyRule:
        attrs = attrs or {}
        for rule in self.rules:
            if rule.match.get("resource_type") == resource_type:
                return rule
            if all(attrs.get(k) == v for k, v in rule.match.items()):
                return rule
        return PolicyRule(name="default", match={"resource_type": resource_type})
