import base64
import concurrent.futures
import json
import stat
import tempfile
import unittest
from pathlib import Path

from urp.adapters import LocalS3Adapter
from urp.ai_gateway import handle_chat_completion, handle_embeddings
from urp.approval_store import ApprovalStore
from urp.auth import APIKeyAuthenticator, Principal, principal_context
from urp.contracts import Contract, LedgerEvent, WorkUnit, WorkUnitKind
from urp.errors import URPError
from urp.executor import execute_work_unit, rehydrate_manifest
from urp.ledger import default_ledger
from urp.manifest_store import FileManifestStore
from urp.package_metadata import write_package_metadata
from urp.release import build_release_manifest, verify_release_manifest, write_release_manifest
from urp.storage import atomic_write_json
from urp.structured_logs import StructuredLogEntry, default_log_store
from urp.service_runtime import create_service_server


class HardeningConformanceTests(unittest.TestCase):
    def test_service_startup_fails_closed_without_configured_auth(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(RuntimeError):
                create_service_server(
                    "control-plane",
                    "127.0.0.1",
                    0,
                    td,
                    authenticator=APIKeyAuthenticator(),
                )

    def test_private_jsonl_files_and_tenant_scoped_direct_reads(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = default_ledger(td)
            ledger.append(LedgerEvent("test", "tenant-a"))
            ledger.append(LedgerEvent("test", "tenant-b"))
            logs = default_log_store(td)
            logs.append(StructuredLogEntry("info", "test", "safe", tenant="tenant-a"))
            logs.append(StructuredLogEntry("info", "test", "safe", tenant="tenant-b"))

            with principal_context(Principal("viewer-a", "tenant-a", {"viewer"})):
                self.assertEqual({event.tenant for event in ledger.read()}, {"tenant-a"})
                self.assertEqual({entry.tenant for entry in logs.read()}, {"tenant-a"})
                self.assertTrue(ledger.verify_chain())

            for name in ("ledger.jsonl", "logs.jsonl"):
                mode = stat.S_IMODE((Path(td) / name).stat().st_mode)
                self.assertEqual(mode & 0o077, 0, name)

    def test_path_traversal_is_rejected_by_stores_and_release_verification(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                FileManifestStore(Path(td) / "manifests").get("../mf_escape")
            with self.assertRaises(ValueError):
                LocalS3Adapter(td).upload_part("../mpu_escape", 1, b"x")

            root = Path(td) / "release"
            root.mkdir()
            (root / "README.md").write_text("safe", encoding="utf-8")
            manifest = build_release_manifest(root)
            manifest["files"] = {"../outside": {"sha256": "0" * 64, "size": 0}}
            from urp.contracts import stable_json_hash

            manifest["content_digest"] = stable_json_hash(manifest["files"])
            with self.assertRaises(ValueError):
                verify_release_manifest(manifest, root)

    def test_release_output_is_stably_self_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("demo", encoding="utf-8")
            first = write_release_manifest(root, "release.json")
            second = write_release_manifest(root, "release.json")
            self.assertEqual(first["files"], second["files"])
            self.assertNotIn("release.json", second["files"])

    def test_generated_package_metadata_excludes_archive_and_itself(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "python" / "urp").mkdir(parents=True)
            (root / "python" / "urp" / "demo.py").write_text("value = 1\n", encoding="utf-8")
            (root / "archive" / "source_packages").mkdir(parents=True)
            (root / "archive" / "source_packages" / "legacy.py").write_text("legacy = 1\n", encoding="utf-8")
            (root / "site").mkdir()
            (root / "site" / "index.html").write_text("generated docs", encoding="utf-8")
            (root / "tmp").mkdir()
            (root / "tmp" / "inspection.txt").write_text("generated inspection", encoding="utf-8")
            result = write_package_metadata(root)
            package = json.loads((root / "package_manifest.json").read_text(encoding="utf-8"))
            lines = json.loads((root / "line_count_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(result["text_file_count"], 1)
            self.assertEqual(package["schema_version"], "urp.package.v2")
            self.assertEqual(lines["line_counts"], {"python/urp/demo.py": 1})

    def test_concurrent_approval_issuance_uses_one_valid_signing_key(self):
        with tempfile.TemporaryDirectory() as td:
            store = ApprovalStore(td)

            def issue(index: int):
                return store.issue(
                    tenant="tenant-a",
                    actor="admin",
                    contract=Contract.EXACT_BYTES,
                    policy_bundle_id="safe-policy",
                    reason=f"concurrent approval {index}",
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                records = list(pool.map(issue, range(24)))
            self.assertEqual(len({record.approval_id for record in records}), 24)
            self.assertTrue(all(store.get(record.approval_id).signature == record.signature for record in records))
            self.assertEqual(stat.S_IMODE((Path(td) / "approval_signing.key").stat().st_mode) & 0o077, 0)

    def test_multipart_parts_are_verified_and_state_gated(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalS3Adapter(td, tenant="tenant-a")
            upload = adapter.create_multipart_upload("bucket", "key")
            adapter.upload_part(upload["upload_id"], 1, b"hello")
            root = Path(td) / "tmp" / "multipart" / upload["upload_id"]
            (root / "part-00000001.bin").write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                adapter.complete_multipart_upload(upload["upload_id"])

            adapter.upload_part(upload["upload_id"], 1, b"hello")
            completed = adapter.complete_multipart_upload(upload["upload_id"])
            self.assertEqual(adapter.get_object(completed["manifest_id"]), b"hello")

            blocked = adapter.create_multipart_upload("bucket", "blocked")
            blocked_root = Path(td) / "tmp" / "multipart" / blocked["upload_id"]
            metadata = json.loads((blocked_root / "meta.json").read_text(encoding="utf-8"))
            metadata["status"] = "completing"
            atomic_write_json(blocked_root / "meta.json", metadata)
            with self.assertRaises(ValueError):
                adapter.upload_part(blocked["upload_id"], 1, b"x")
            with self.assertRaises(ValueError):
                adapter.abort_multipart_upload(blocked["upload_id"])

    def test_manifest_codec_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = execute_work_unit(
                WorkUnit(WorkUnitKind.BYTE_OBJECT, "tenant-a", "s3://bucket/compressed", b"A" * 100_000),
                td,
            )
            path = Path(td) / "manifests" / f"{result.manifest_id}.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            compressed = next(segment for segment in manifest["physical"]["segments"] if "zstd" in segment["transform_stack"])
            compressed["codec"] = "unsupported-codec"
            atomic_write_json(path, manifest)
            with self.assertRaises(URPError) as error:
                rehydrate_manifest(result.manifest_id, td)
            self.assertEqual(error.exception.code, "rehydration_failed")

    def test_ai_context_is_applied_and_high_risk_routes_to_strongest_model(self):
        class CapturingProvider:
            def __init__(self):
                self.requests = []
                self.routes = []

            def chat(self, request, route):
                self.requests.append(request)
                self.routes.append(route)
                return {
                    "id": "chatcmpl_capture",
                    "object": "chat.completion",
                    "model": route,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Seek qualified professional help."},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                }

        with tempfile.TemporaryDirectory() as td:
            provider = CapturingProvider()
            response = handle_chat_completion(
                {
                    "model": "auto",
                    "messages": [
                        {"role": "system", "content": "Use the approved policy."},
                        {"role": "system", "content": "Use the approved policy."},
                        {"role": "user", "content": "Give medical diagnosis for this emergency."},
                    ],
                },
                tenant="tenant-ai",
                state_dir=td,
                provider=provider,
            )
            sent_system = [row for row in provider.requests[0]["messages"] if row["role"] == "system"]
            self.assertEqual(len(sent_system), 1)
            self.assertEqual(provider.routes, ["frontier"])
            self.assertTrue(response["urp"]["context_applied"])

    def test_base64_embeddings_have_requested_dimensions_and_cache(self):
        with tempfile.TemporaryDirectory() as td:
            request = {
                "model": "mock-embedding",
                "input": ["alpha", "beta"],
                "encoding_format": "base64",
                "dimensions": 12,
            }
            first = handle_embeddings(request, tenant="tenant-vector", state_dir=td)
            second = handle_embeddings(request, tenant="tenant-vector", state_dir=td)
            for row in first["data"]:
                self.assertEqual(len(base64.b64decode(row["embedding"], validate=True)), 12 * 4)
            self.assertEqual(first["urp"]["cache"], "miss")
            self.assertEqual(second["urp"]["cache"], "exact_hit")


if __name__ == "__main__":
    unittest.main()
