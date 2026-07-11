from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List


PATTERNS = [
    ("uuid", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    ("ip", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("hex", re.compile(r"\b0x[0-9a-f]+\b", re.I)),
    ("number", re.compile(r"\b\d+\b")),
]


@dataclass(frozen=True)
class LogTemplate:
    template: str
    variables: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {"template": self.template, "variables": self.variables}


def extract_log_template(line: str) -> LogTemplate:
    variables: List[Dict[str, str]] = []
    templated = line
    for name, pattern in PATTERNS:
        def repl(match: re.Match[str]) -> str:
            variables.append({"name": name, "value": match.group(0)})
            return f"<{name}>"

        templated = pattern.sub(repl, templated)
    return LogTemplate(templated, variables)


def group_log_templates(lines: List[str]) -> Dict[str, Dict[str, object]]:
    groups: Dict[str, Dict[str, object]] = {}
    for line in lines:
        extracted = extract_log_template(line)
        row = groups.setdefault(extracted.template, {"count": 0, "variables": []})
        row["count"] = int(row["count"]) + 1
        row["variables"].append(extracted.variables)
    return groups
