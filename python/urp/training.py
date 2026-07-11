from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .contracts import stable_json_hash


@dataclass(frozen=True)
class TrainingSample:
    sample_id: str
    text: str
    metadata: Dict[str, object] = field(default_factory=dict)

    def fingerprint(self) -> str:
        return stable_json_hash({"text": " ".join(self.text.split()), "metadata": self.metadata})

    def to_dict(self) -> Dict[str, object]:
        return {"sample_id": self.sample_id, "text": self.text, "metadata": self.metadata}


@dataclass(frozen=True)
class TrainingReductionResult:
    accepted: bool
    unique_samples: List[TrainingSample]
    duplicate_map: Dict[str, str]
    bytes_avoided: int
    verifier: str = "dataset_lineage"
    rollback: str = "reconstruct original sample order from duplicate map"

    def to_dict(self) -> Dict[str, object]:
        return {
            "accepted": self.accepted,
            "unique_samples": [sample.to_dict() for sample in self.unique_samples],
            "duplicate_map": self.duplicate_map,
            "bytes_avoided": self.bytes_avoided,
            "verifier": self.verifier,
            "rollback": self.rollback,
        }


def dedupe_training_samples(samples: List[TrainingSample]) -> TrainingReductionResult:
    seen: Dict[str, TrainingSample] = {}
    unique: List[TrainingSample] = []
    duplicate_map: Dict[str, str] = {}
    bytes_avoided = 0
    for sample in samples:
        fp = sample.fingerprint()
        if fp in seen:
            duplicate_map[sample.sample_id] = seen[fp].sample_id
            bytes_avoided += len(sample.text.encode("utf-8"))
            continue
        seen[fp] = sample
        unique.append(sample)
    return TrainingReductionResult(bool(duplicate_map), unique, duplicate_map, bytes_avoided)
