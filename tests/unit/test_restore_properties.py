"""Property tests for exact restore.

The checked-in corpus under tests/fixtures/restore_corpus is a compatibility
fixture produced by this version's local object path. It is not a benchmark.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule

from urp.adapters import LocalS3Adapter
from urp.chunk_store import LocalChunkStore
from urp.chunking import content_defined_chunks, fixed_chunks
from urp.executor import rehydrate_manifest, rehydrate_manifest_range
from urp.transforms import ZstdLikePlugin

CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "restore_corpus"
PAYLOADS = st.binary(max_size=4096)


def _segments(chunks, stored):
    rows = []
    for chunk, stored_chunk in zip(chunks, stored):
        row = stored_chunk.to_dict()
        row.update({"logical_start": chunk.start, "logical_end": chunk.end, "sha256": chunk.sha256})
        rows.append(row)
    return rows


def _assert_range(payload: bytes, restored: bytes, start: int, end: int) -> None:
    start = min(start, len(payload))
    end = min(max(end, start), len(payload))
    assert restored == payload
    assert payload[start:end] == restored[start:end]


class ChunkRestorePropertyTest(unittest.TestCase):
    @settings(max_examples=20, deadline=None)
    @given(payload=PAYLOADS, chunk_size=st.integers(min_value=1, max_value=128), compress=st.booleans(), start=st.integers(min_value=0, max_value=4096), end=st.integers(min_value=0, max_value=4096))
    def test_fixed_chunks_roundtrip_including_zlib(self, payload, chunk_size, compress, start, end):
        with tempfile.TemporaryDirectory() as td:
            store = LocalChunkStore(Path(td) / "chunks")
            chunks = fixed_chunks(payload, chunk_size) if payload else []
            stored = store.put_chunks("tenant", "ns", chunks, compress=compress)
            restored = store.rehydrate(_segments(chunks, stored))
            _assert_range(payload, restored, start, end)
            for segment in _segments(chunks, stored):
                if segment.get("codec") not in {None, "zlib", "zstd"}:
                    raise AssertionError(segment.get("codec"))

    @settings(max_examples=15, deadline=None)
    @given(payload=PAYLOADS, start=st.integers(min_value=0, max_value=4096), end=st.integers(min_value=0, max_value=4096))
    def test_content_defined_chunks_roundtrip(self, payload, start, end):
        with tempfile.TemporaryDirectory() as td:
            store = LocalChunkStore(Path(td) / "chunks")
            chunks = content_defined_chunks(payload, min_size=8, avg_bits=3, max_size=64) if payload else []
            stored = store.put_chunks("tenant", "ns", chunks, compress=True)
            restored = store.rehydrate(_segments(chunks, stored))
            _assert_range(payload, restored, start, end)

    def test_zlib_codec_roundtrip_is_explicit(self):
        plugin = ZstdLikePlugin(codec="zlib")
        raw = b"prefix-cache-safe" * 20
        encoded = plugin.compress(raw)
        self.assertEqual(plugin.decompress(encoded), raw)
        self.assertEqual(plugin.codec, "zlib")


class ObjectRestoreMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self._td = tempfile.TemporaryDirectory()
        self.adapter = LocalS3Adapter(self._td.name, tenant="prop")
        self.objects: dict[str, bytes] = {}

    def teardown(self):
        self._td.cleanup()

    @rule(body=st.binary(max_size=2048))
    def put(self, body):
        result = self.adapter.put_object("bucket", f"k{len(self.objects)}", body)
        self.objects[result["manifest_id"]] = body
        assert self.adapter.get_object(result["manifest_id"]) == body

    @rule(parts=st.lists(st.binary(max_size=256), min_size=1, max_size=4))
    def multipart(self, parts):
        upload = self.adapter.create_multipart_upload("bucket", f"mp{len(self.objects)}")
        order = list(range(1, len(parts) + 1))
        for part_number in reversed(order):
            self.adapter.upload_part(upload["upload_id"], part_number, parts[part_number - 1])
        completed = self.adapter.complete_multipart_upload(upload["upload_id"])
        body = b"".join(parts)
        self.objects[completed["manifest_id"]] = body
        assert self.adapter.get_object(completed["manifest_id"]) == body

    @rule(start=st.integers(min_value=0, max_value=2048), end=st.integers(min_value=0, max_value=2304))
    def range_read(self, start, end):
        if not self.objects:
            return
        manifest_id = next(reversed(self.objects))
        body = self.objects[manifest_id]
        start = min(start, len(body))
        end = min(max(end, start), len(body))
        assert self.adapter.range_read(manifest_id, start, end) == body[start:end]
        assert self.adapter.get_object(manifest_id) == body


TestObjectRestoreMachine = ObjectRestoreMachine.TestCase
TestObjectRestoreMachine.settings = settings(max_examples=8, stateful_step_count=6, deadline=None)


class FrozenRestoreCorpusTest(unittest.TestCase):
    def test_checked_in_manifests_still_restore(self):
        index = json.loads((CORPUS / "corpus.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(index["cases"]), 2)
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            shutil.copytree(CORPUS / "state", state)
            for case in index["cases"]:
                original = (CORPUS / "originals" / case["file"]).read_bytes()
                digest = hashlib.sha256(original).hexdigest()
                self.assertEqual(digest, case["sha256"])
                restored = rehydrate_manifest(case["manifest_id"], state)
                self.assertEqual(restored, original)
                for start, end in case["ranges"]:
                    self.assertEqual(rehydrate_manifest_range(case["manifest_id"], start, end, state), original[start:end])


if __name__ == "__main__":
    unittest.main()
