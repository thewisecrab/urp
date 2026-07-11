from __future__ import annotations

from typing import Dict, List
from .contracts import Manifest


class InMemoryManifestStore:
    def __init__(self) -> None:
        self._by_id: Dict[str, Manifest] = {}
        self._by_work_unit: Dict[str, str] = {}

    def put(self, manifest: Manifest) -> None:
        self._by_id[manifest.manifest_id] = manifest
        self._by_work_unit[manifest.work_unit_id] = manifest.manifest_id

    def get(self, manifest_id: str) -> Manifest:
        return self._by_id[manifest_id]

    def get_by_work_unit(self, work_unit_id: str) -> Manifest:
        return self._by_id[self._by_work_unit[work_unit_id]]

    def list(self) -> List[Manifest]:
        return list(self._by_id.values())
