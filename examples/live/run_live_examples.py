#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from urp.adapters import LocalS3Adapter, MockContractAdapter
from urp.ai_gateway import handle_chat_completion
from urp.contracts import WorkUnitKind
from urp.executor import init_state
from urp.ledger import default_ledger
from urp.manifest_explorer import manifest_explorer_report
from urp.manifest_store import default_manifest_store
from urp.reports import dashboard_report, savings_report


OBJECT_PAYLOAD = (
    b"timestamp,service,status,latency_ms\n"
    + b"2026-07-08T10:00:00Z,gateway,200,41\n" * 160
    + b"2026-07-08T10:01:00Z,gateway,200,39\n" * 160
)


def run_live_examples(state_dir: str | Path, reset: bool = False) -> Dict[str, Any]:
    state = Path(state_dir)
    if reset and state.exists():
        shutil.rmtree(state)
    init_state(state)

    object_case = _object_gateway_case(state)
    ai_case = _ai_gateway_case(state)
    adapter_case = _adapter_case(state)
    report_case = _report_case(state)

    ledger = default_ledger(state)
    manifest_store = default_manifest_store(state)
    return {
        "state_dir": str(state),
        "summary": {
            "live_examples": ["object_gateway_exact", "ai_gateway_exact_cache", "lakehouse_mock_adapter", "reports_and_audit"],
            "manifests": len(manifest_store.list()),
            "ledger_events": len(ledger.read()),
            "ledger_chain_valid": ledger.verify_chain(),
            "external_services_required": False,
        },
        "object_gateway_exact": object_case,
        "ai_gateway_exact_cache": ai_case,
        "lakehouse_mock_adapter": adapter_case,
        "reports_and_audit": report_case,
    }


def _object_gateway_case(state: Path) -> Dict[str, Any]:
    adapter = LocalS3Adapter(state, tenant="acme")
    put = adapter.put_object(
        "acme-observability",
        "logs/2026-07-08/gateway.csv",
        OBJECT_PAYLOAD,
        metadata={"content-type": "text/csv", "owner": "platform"},
        tags={"classification": "ops", "legal_hold": "true"},
    )
    manifest = default_manifest_store(state).get(put["manifest_id"])
    head = adapter.head_object(put["manifest_id"])
    full = adapter.get_object(put["manifest_id"])
    ranged = adapter.range_read(put["manifest_id"], 0, 32)
    delete = adapter.delete_object(put["manifest_id"], actor="example", allow_delete=True)
    events = [event.event_type for event in default_ledger(state).query(work_unit_id=put["work_unit_id"])]
    return {
        "use_case": "S3-compatible exact object ingestion with legal-hold guardrail",
        "manifest_id": put["manifest_id"],
        "work_unit_id": put["work_unit_id"],
        "etag": put["etag"],
        "logical_size": manifest.physical["logical_size"],
        "stored_size": manifest.physical["stored_size"],
        "rehydrated_exact": full == OBJECT_PAYLOAD,
        "range_preview": ranged.decode("utf-8", errors="replace"),
        "head": head,
        "delete_guardrail": delete,
        "ledger_events": events,
    }


def _ai_gateway_case(state: Path) -> Dict[str, Any]:
    request = {
        "model": "auto",
        "messages": [
            {"role": "system", "content": "source:vpn-runbook:v1"},
            {"role": "user", "content": "Summarize the VPN reset policy for tier-1 support."},
        ],
        "urp": {"source_fingerprints": ["kb:vpn-runbook:v1"], "max_context_tokens": 64},
    }
    first = handle_chat_completion(request, tenant="acme", namespace="support", state_dir=state)
    second = handle_chat_completion(request, tenant="acme", namespace="support", state_dir=state)
    first_manifest = default_manifest_store(state).get(first["urp"]["manifest_id"])
    second_manifest = default_manifest_store(state).get(second["urp"]["manifest_id"])
    return {
        "use_case": "OpenAI-compatible chat gateway with exact cache and compute manifests",
        "first_cache": first["urp"]["cache"],
        "second_cache": second["urp"]["cache"],
        "first_route": first["urp"]["route"],
        "second_route": second["urp"]["route"],
        "provider_avoided_on_second_call": not second_manifest.telemetry["provider_called"],
        "raw_prompt_logged": first_manifest.classification["raw_prompt_logged"],
        "first_manifest_id": first["urp"]["manifest_id"],
        "second_manifest_id": second["urp"]["manifest_id"],
        "compute_manifest": {
            "task_type": first_manifest.physical["compute_manifest"]["request"]["task_type"],
            "accepted_by_verifier": first_manifest.physical["compute_manifest"]["result"]["accepted_by_verifier"],
            "cache_result": first_manifest.physical["cache_result"],
        },
    }


def _adapter_case(state: Path) -> Dict[str, Any]:
    adapter = MockContractAdapter("lakehouse", [WorkUnitKind.TABLE_SNAPSHOT, WorkUnitKind.STRUCTURED_FILE], state_dir=state, tenant="acme")
    result = adapter.execute_kind(
        WorkUnitKind.TABLE_SNAPSHOT,
        "lakehouse://sales/orders/snapshot-2026-07-08",
        payload={"snapshot_id": "snap-2026-07-08", "files": ["orders-0001.parquet", "orders-0002.parquet"], "rows": 120000},
        requested_contract="exact_logical",
        metadata={"table": "sales.orders", "format": "iceberg"},
    )
    restored = adapter.rehydrate(result["manifest_id"]).decode("utf-8")
    manifest = default_manifest_store(state).get(result["manifest_id"])
    return {
        "use_case": "Lakehouse adapter contract exercised locally without external services",
        "adapter": result["adapter"],
        "kind": result["kind"],
        "accepted": result["accepted"],
        "manifest_id": result["manifest_id"],
        "contract": manifest.contract.value,
        "external_integrations_required": adapter.capabilities()["external_integrations_required"],
        "rehydrated_contains_snapshot_id": "snap-2026-07-08" in restored,
    }


def _report_case(state: Path) -> Dict[str, Any]:
    explorer = manifest_explorer_report(state, tenant="acme", redacted=True)
    savings = savings_report(state, tenant="acme")
    dashboard = dashboard_report(state, tenant="acme")
    return {
        "use_case": "Audit, manifest explorer, and dashboard evidence from the same local run",
        "manifest_explorer": {
            "count": explorer["manifest_count"],
            "by_kind": explorer["by_kind"],
            "redacted": explorer["filters"]["redacted"],
        },
        "savings": savings,
        "dashboard_sections": [section for section in ("executive", "platform", "ai", "data", "security") if section in dashboard],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run URP local live examples and print JSON evidence.")
    parser.add_argument("--state-dir", default=".urp-live-examples")
    parser.add_argument("--reset", action="store_true", help="Delete the state directory before running.")
    args = parser.parse_args()
    print(json.dumps(run_live_examples(args.state_dir, reset=args.reset), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
