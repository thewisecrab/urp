from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .contracts import stable_json_hash


@dataclass(frozen=True)
class LakehouseFile:
    path: str
    partition: str
    size_bytes: int
    row_count: int = 0
    fingerprint: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "partition": self.partition,
            "size_bytes": self.size_bytes,
            "row_count": self.row_count,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class CompactionGroup:
    partition: str
    input_paths: List[str]
    output_ref: str
    total_bytes: int
    total_rows: int
    files_avoided: int
    verifier: str = "snapshot_equivalence"
    rollback: str = "restore previous table snapshot pointer"

    def to_dict(self) -> Dict[str, object]:
        return {
            "partition": self.partition,
            "input_paths": self.input_paths,
            "output_ref": self.output_ref,
            "total_bytes": self.total_bytes,
            "total_rows": self.total_rows,
            "files_avoided": self.files_avoided,
            "verifier": self.verifier,
            "rollback": self.rollback,
        }


@dataclass(frozen=True)
class LakehouseOptimizationPlan:
    accepted: bool
    groups: List[CompactionGroup] = field(default_factory=list)
    reason: str = "no_small_file_groups"

    def to_dict(self) -> Dict[str, object]:
        return {"accepted": self.accepted, "reason": self.reason, "groups": [group.to_dict() for group in self.groups]}


def recommend_compaction(
    files: List[LakehouseFile],
    target_file_size: int = 128 * 1024 * 1024,
    min_group_size: int = 2,
) -> LakehouseOptimizationPlan:
    by_partition: Dict[str, List[LakehouseFile]] = {}
    for item in files:
        if item.size_bytes <= 0:
            continue
        if item.size_bytes < target_file_size:
            by_partition.setdefault(item.partition, []).append(item)
    groups: List[CompactionGroup] = []
    for partition, candidates in sorted(by_partition.items()):
        if len(candidates) < min_group_size:
            continue
        total_bytes = sum(item.size_bytes for item in candidates)
        total_rows = sum(item.row_count for item in candidates)
        digest = stable_json_hash({"partition": partition, "paths": [item.path for item in candidates], "bytes": total_bytes})[:16]
        groups.append(
            CompactionGroup(
                partition=partition,
                input_paths=[item.path for item in candidates],
                output_ref=f"compact://{partition}/{digest}",
                total_bytes=total_bytes,
                total_rows=total_rows,
                files_avoided=max(0, len(candidates) - 1),
            )
        )
    return LakehouseOptimizationPlan(bool(groups), groups, "small_file_groups_found" if groups else "no_small_file_groups")
