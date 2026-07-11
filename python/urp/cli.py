from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .ai_router import RouteFeedbackStore
from .ai_gateway import MockProvider, OpenAICompatibleProvider, handle_chat_completion
from .approval_store import ApprovalStore
from .benchmarks import run_benchmark_suite
from .conformance import ai_gateway_conformance
from .contracts import LedgerEvent, WorkUnit, WorkUnitKind, Contract
from .encoding import json_safe_work_unit
from .disaster_recovery import export_state, import_state
from .executor import execute_work_unit, init_state, rehydrate_manifest, rehydrate_manifest_range
from .kms import LocalKMS
from .impact import load_impact_scenario, model_impact
from .ledger import default_ledger
from .manifest_explorer import manifest_explorer_report
from .manifest_store import default_manifest_store, redact_manifest
from .package_metadata import write_package_metadata
from .plan_store import store_plan_with_audit
from .platforms import built_in_platform_profiles, platform_matrix, platform_readiness
from .planner import plan_work_unit
from .plugins import PluginRegistry, adapter_conformance, discover_plugin_packages, plugin_package_conformance
from .adapters import built_in_adapters
from .policy import load_policy_bundle, validate_policy_bundle
from .policy_store import PolicyBundleStore, resolve_active_policy_bundle
from .production import production_readiness_check
from .release import verify_release_manifest, write_release_manifest
from .reports import dashboard_report, savings_report
from .service_runtime import create_service_server, serve_service, service_health, service_specs
from .structured_logs import default_log_store
from .storage import atomic_write_bytes
from .tracing import default_trace_store
from .work_unit_store import default_work_unit_store


def main() -> None:
    parser = argparse.ArgumentParser(prog="urp", description="URP reference CLI")
    parser.add_argument("--state-dir", default=".urp")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")

    plan = sub.add_parser("plan")
    plan.add_argument("--kind", required=True)
    plan.add_argument("--tenant", default="local")
    plan.add_argument("--logical-ref", default="cli://input")
    plan.add_argument("--input", default="")
    plan.add_argument("--file", default=None)
    plan.add_argument("--contract", default=None)

    execute = sub.add_parser("execute")
    execute.add_argument("--kind", required=True)
    execute.add_argument("--tenant", default="local")
    execute.add_argument("--logical-ref", default="cli://input")
    execute.add_argument("--input", default="")
    execute.add_argument("--file", default=None)
    execute.add_argument("--contract", default=None)
    execute.add_argument("--mode", default=None, choices=["observe", "shadow", "enforce"])

    manifest = sub.add_parser("manifest")
    manifest_sub = manifest.add_subparsers(dest="manifest_cmd", required=True)
    manifest_get = manifest_sub.add_parser("get")
    manifest_get.add_argument("manifest_id")
    manifest_list = manifest_sub.add_parser("list")
    manifest_list.add_argument("--logical-ref", default=None)
    manifest_list.add_argument("--tenant", default=None)
    manifest_list.add_argument("--redacted", action="store_true")
    manifest_export = manifest_sub.add_parser("export")
    manifest_export.add_argument("--logical-ref", default=None)
    manifest_export.add_argument("--tenant", default=None)
    manifest_export.add_argument("--redacted", action="store_true", default=True)
    manifest_export.add_argument("--full", dest="redacted", action="store_false")
    manifest_explore = manifest_sub.add_parser("explore")
    manifest_explore.add_argument("--tenant", default=None)
    manifest_explore.add_argument("--kind", default=None)
    manifest_explore.add_argument("--contract", default=None)
    manifest_explore.add_argument("--state", default=None)
    manifest_explore.add_argument("--limit", type=int, default=None)
    manifest_explore.add_argument("--redacted", action="store_true", default=True)
    manifest_explore.add_argument("--full", dest="redacted", action="store_false")
    manifest_rehydrate = manifest_sub.add_parser("rehydrate")
    manifest_rehydrate.add_argument("manifest_id")
    manifest_rehydrate.add_argument("--output", default=None)
    manifest_rehydrate.add_argument("--range", dest="byte_range", default=None, help="Optional byte range as start:end")

    work_unit = sub.add_parser("work-unit")
    work_unit_sub = work_unit.add_subparsers(dest="work_unit_cmd", required=True)
    work_unit_create = work_unit_sub.add_parser("create")
    _add_work_unit_args(work_unit_create)
    work_unit_list = work_unit_sub.add_parser("list")
    work_unit_list.add_argument("--tenant", default=None)
    work_unit_get = work_unit_sub.add_parser("get")
    work_unit_get.add_argument("work_unit_id")
    work_unit_plan = work_unit_sub.add_parser("plan")
    work_unit_plan.add_argument("work_unit_id")
    work_unit_execute = work_unit_sub.add_parser("execute")
    work_unit_execute.add_argument("work_unit_id")
    work_unit_execute.add_argument("--mode", default=None, choices=["observe", "shadow", "enforce"])

    ledger = sub.add_parser("ledger")
    ledger_sub = ledger.add_subparsers(dest="ledger_cmd", required=True)
    ledger_query = ledger_sub.add_parser("query")
    ledger_query.add_argument("--tenant", default=None)
    ledger_query.add_argument("--work-unit-id", default=None)
    ledger_query.add_argument("--manifest-id", default=None)
    ledger_query.add_argument("--event-type", dest="event_type", action="append", default=None)
    ledger_query.add_argument("--event-types", default=None, help="Comma-separated event types")
    ledger_query.add_argument("--last", type=int, default=None)

    trace = sub.add_parser("trace")
    trace_sub = trace.add_subparsers(dest="trace_cmd", required=True)
    trace_query = trace_sub.add_parser("query")
    trace_query.add_argument("--trace-id", default=None)
    trace_query.add_argument("--name", default=None)

    logs = sub.add_parser("logs")
    logs_sub = logs.add_subparsers(dest="logs_cmd", required=True)
    logs_query = logs_sub.add_parser("query")
    logs_query.add_argument("--tenant", default=None)
    logs_query.add_argument("--work-unit-id", default=None)
    logs_query.add_argument("--manifest-id", default=None)
    logs_query.add_argument("--event-type", dest="event_type", action="append", default=None)
    logs_query.add_argument("--event-types", default=None, help="Comma-separated event types")
    logs_query.add_argument("--trace-id", default=None)
    logs_query.add_argument("--severity", default=None)
    logs_query.add_argument("--error-code", default=None)
    logs_query.add_argument("--last", type=int, default=None)

    report = sub.add_parser("report")
    report_sub = report.add_subparsers(dest="report_cmd", required=True)
    report_savings = report_sub.add_parser("savings")
    report_savings.add_argument("--tenant", default=None)
    report_dashboard = report_sub.add_parser("dashboard")
    report_dashboard.add_argument("--tenant", default=None)
    report_sub.add_parser("routes")
    report_impact = report_sub.add_parser("impact")
    report_impact.add_argument("--scenario", required=True, help="Path to an impact scenario JSON file")

    platform = sub.add_parser("platform")
    platform_sub = platform.add_subparsers(dest="platform_cmd", required=True)
    platform_sub.add_parser("list")
    platform_matrix_cmd = platform_sub.add_parser("matrix")
    platform_matrix_cmd.add_argument("--require-live", action="store_true")
    platform_validate = platform_sub.add_parser("validate")
    platform_validate.add_argument("--target", default="all")
    platform_validate.add_argument("--require-live", action="store_true")

    conformance = sub.add_parser("conformance")
    conformance_sub = conformance.add_subparsers(dest="conformance_cmd", required=True)
    conformance_sub.add_parser("ai")
    conformance_adapters = conformance_sub.add_parser("adapters")
    conformance_adapters.add_argument("--adapter", default=None)
    conformance_plugins = conformance_sub.add_parser("plugins")
    conformance_plugins.add_argument("--package", dest="plugin_package", default=None)
    conformance_plugins.add_argument("--all-packages", action="store_true")

    policy = sub.add_parser("policy")
    policy_sub = policy.add_subparsers(dest="policy_cmd", required=True)
    policy_validate = policy_sub.add_parser("validate")
    policy_validate.add_argument("path")
    policy_publish = policy_sub.add_parser("publish")
    policy_publish.add_argument("path")
    policy_publish.add_argument("--actor", default="system")
    policy_sub.add_parser("list")
    policy_active = policy_sub.add_parser("active")
    policy_active.add_argument("--name", default="default-safe")
    policy_reload = policy_sub.add_parser("reload")
    policy_reload.add_argument("--name", default="default-safe")
    policy_reload.add_argument("--actor", default="system")
    policy_rollback = policy_sub.add_parser("rollback")
    policy_rollback.add_argument("--name", required=True)
    policy_rollback.add_argument("--version", required=True)
    policy_rollback.add_argument("--actor", default="system")

    approval = sub.add_parser("approval")
    approval_sub = approval.add_subparsers(dest="approval_cmd", required=True)
    approval_issue = approval_sub.add_parser("issue")
    approval_issue.add_argument("--tenant", required=True)
    approval_issue.add_argument("--contract", required=True, choices=[contract.value for contract in Contract])
    approval_issue.add_argument("--policy-bundle-id", required=True)
    approval_issue.add_argument("--reason", required=True)
    approval_issue.add_argument("--work-unit-id", default=None)
    approval_issue.add_argument("--ttl-seconds", type=int, default=900)
    approval_issue.add_argument("--actor", default="cli-admin")
    approval_list = approval_sub.add_parser("list")
    approval_list.add_argument("--tenant", default=None)
    approval_get = approval_sub.add_parser("get")
    approval_get.add_argument("approval_id")

    plugin = sub.add_parser("plugin")
    plugin_sub = plugin.add_subparsers(dest="plugin_cmd", required=True)
    plugin_register = plugin_sub.add_parser("register")
    plugin_register.add_argument("descriptor_json")
    plugin_register.add_argument("--actor", default="system")
    plugin_sub.add_parser("list")
    plugin_conformance = plugin_sub.add_parser("conformance")
    plugin_conformance.add_argument("--adapter", default=None)
    plugin_conformance.add_argument("--package", dest="plugin_package", default=None)
    plugin_conformance.add_argument("--all-packages", action="store_true")

    kms = sub.add_parser("kms")
    kms_sub = kms.add_subparsers(dest="kms_cmd", required=True)
    kms_create = kms_sub.add_parser("create-key")
    kms_create.add_argument("--purpose", default="local-dev")
    kms_encrypt = kms_sub.add_parser("encrypt")
    kms_encrypt.add_argument("--key-id", required=True)
    kms_encrypt.add_argument("--text", required=True)
    kms_decrypt = kms_sub.add_parser("decrypt")
    kms_decrypt.add_argument("--envelope-json", required=True)

    dr = sub.add_parser("dr")
    dr_sub = dr.add_subparsers(dest="dr_cmd", required=True)
    dr_export = dr_sub.add_parser("export")
    dr_export.add_argument("--output", required=True)
    dr_import = dr_sub.add_parser("import")
    dr_import.add_argument("--archive", required=True)
    dr_import.add_argument("--replace", action="store_true")

    admin = sub.add_parser("admin")
    admin_sub = admin.add_subparsers(dest="admin_cmd", required=True)
    admin_readiness = admin_sub.add_parser("readiness")
    admin_readiness.add_argument("--use-state-dir", action="store_true", help="Run against --state-dir instead of an isolated temporary state")

    gateway = sub.add_parser("gateway")
    gateway_sub = gateway.add_subparsers(dest="gateway_cmd", required=True)
    gateway_ai = gateway_sub.add_parser("ai")
    gateway_ai.add_argument("--provider", default="mock")
    gateway_ai.add_argument("--listen", default="127.0.0.1:8080")
    gateway_ai.add_argument("--once-json", default=None)
    gateway_ai.add_argument("--serve", action="store_true")

    benchmark = sub.add_parser("benchmark")
    benchmark_sub = benchmark.add_subparsers(dest="benchmark_cmd", required=True)
    benchmark_run = benchmark_sub.add_parser("run")
    benchmark_run.add_argument("--suite", required=True)

    service = sub.add_parser("service")
    service_sub = service.add_subparsers(dest="service_cmd", required=True)
    service_sub.add_parser("list")
    service_health_cmd = service_sub.add_parser("health")
    service_health_cmd.add_argument("--name", required=True)
    service_run = service_sub.add_parser("run")
    service_run.add_argument("--name", required=True)
    service_run.add_argument("--listen", default="127.0.0.1:8080")

    release = sub.add_parser("release")
    release_sub = release.add_subparsers(dest="release_cmd", required=True)
    release_sign = release_sub.add_parser("sign")
    release_sign.add_argument("--output", default="PACKAGE_SHA256.json")
    release_verify = release_sub.add_parser("verify")
    release_verify.add_argument("--manifest", default="PACKAGE_SHA256.json")
    release_verify.add_argument("--root", default=".")
    release_verify.add_argument("--require-signature", action="store_true")
    release_metadata = release_sub.add_parser("metadata")
    release_metadata.add_argument("--root", default=".")

    args = parser.parse_args()

    if args.cmd == "init":
        state = init_state(args.state_dir)
        print(json.dumps({"initialized": str(state)}, indent=2))
    elif args.cmd == "plan":
        wu = _work_unit_from_args(args)
        plan_result = plan_work_unit(wu, policy_bundle=_active_policy(args.state_dir, wu))
        store_plan_with_audit(args.state_dir, plan_result, wu, actor="cli")
        print(json.dumps(plan_result.to_dict(), indent=2))
    elif args.cmd == "execute":
        wu = _work_unit_from_args(args)
        print(json.dumps(execute_work_unit(wu, args.state_dir, args.mode).to_dict(), indent=2))
    elif args.cmd == "manifest" and args.manifest_cmd == "get":
        print(json.dumps(default_manifest_store(args.state_dir).get(args.manifest_id).to_dict(), indent=2))
    elif args.cmd == "manifest" and args.manifest_cmd == "list":
        store = default_manifest_store(args.state_dir)
        rows = store.find_by_logical_ref(args.logical_ref) if args.logical_ref else store.list()
        if args.tenant:
            rows = [row for row in rows if row.tenant == args.tenant]
        payload = [redact_manifest(row) if args.redacted else row.to_dict() for row in rows]
        print(json.dumps(payload, indent=2))
    elif args.cmd == "manifest" and args.manifest_cmd == "export":
        store = default_manifest_store(args.state_dir)
        rows = store.find_by_logical_ref(args.logical_ref) if args.logical_ref else store.list()
        if args.tenant:
            rows = [row for row in rows if row.tenant == args.tenant]
        payload = [redact_manifest(row) if args.redacted else row.to_dict() for row in rows]
        print(json.dumps({"manifest_count": len(payload), "redacted": args.redacted, "manifests": payload}, indent=2))
    elif args.cmd == "manifest" and args.manifest_cmd == "explore":
        print(
            json.dumps(
                manifest_explorer_report(
                    args.state_dir,
                    tenant=args.tenant,
                    kind=args.kind,
                    contract=args.contract,
                    state=args.state,
                    limit=args.limit,
                    redacted=args.redacted,
                ),
                indent=2,
            )
        )
    elif args.cmd == "manifest" and args.manifest_cmd == "rehydrate":
        if args.byte_range:
            start, end = _parse_byte_range(args.byte_range)
            data = rehydrate_manifest_range(args.manifest_id, start, end, args.state_dir)
        else:
            data = rehydrate_manifest(args.manifest_id, args.state_dir)
        if args.output:
            atomic_write_bytes(args.output, data)
            payload = {"manifest_id": args.manifest_id, "output": args.output, "bytes": len(data)}
            if args.byte_range:
                payload["range"] = args.byte_range
            print(json.dumps(payload, indent=2))
        else:
            try:
                print(data.decode("utf-8"))
            except UnicodeDecodeError:
                print(json.dumps({"manifest_id": args.manifest_id, "bytes": len(data), "hex": data.hex()}, indent=2))
    elif args.cmd == "work-unit" and args.work_unit_cmd == "create":
        wu = _work_unit_from_args(args)
        default_work_unit_store(args.state_dir).put(wu)
        default_ledger(args.state_dir).append(LedgerEvent("work_unit.created", wu.tenant, wu.id, trace_id=wu.trace_id))
        print(json.dumps({"work_unit_id": wu.id, "trace_id": wu.trace_id, "state": "received"}, indent=2))
    elif args.cmd == "work-unit" and args.work_unit_cmd == "list":
        print(json.dumps([json_safe_work_unit(wu) for wu in default_work_unit_store(args.state_dir).list(args.tenant)], indent=2))
    elif args.cmd == "work-unit" and args.work_unit_cmd == "get":
        print(json.dumps(json_safe_work_unit(default_work_unit_store(args.state_dir).get(args.work_unit_id)), indent=2))
    elif args.cmd == "work-unit" and args.work_unit_cmd == "plan":
        wu = default_work_unit_store(args.state_dir).get(args.work_unit_id)
        plan_result = plan_work_unit(wu, policy_bundle=_active_policy(args.state_dir, wu))
        store_plan_with_audit(args.state_dir, plan_result, wu, actor="cli")
        print(json.dumps(plan_result.to_dict(), indent=2))
    elif args.cmd == "work-unit" and args.work_unit_cmd == "execute":
        print(json.dumps(execute_work_unit(default_work_unit_store(args.state_dir).get(args.work_unit_id), args.state_dir, args.mode).to_dict(), indent=2))
    elif args.cmd == "ledger" and args.ledger_cmd == "query":
        rows = default_ledger(args.state_dir).query(
            args.tenant,
            args.work_unit_id,
            args.manifest_id,
            event_types=_event_types_from_args(args),
            limit=args.last,
        )
        print(json.dumps([row.to_dict() for row in rows], indent=2))
    elif args.cmd == "trace" and args.trace_cmd == "query":
        print(json.dumps([span.to_dict() for span in default_trace_store(args.state_dir).query(args.trace_id, args.name)], indent=2))
    elif args.cmd == "logs" and args.logs_cmd == "query":
        rows = default_log_store(args.state_dir).query(
            tenant=args.tenant,
            work_unit_id=args.work_unit_id,
            manifest_id=args.manifest_id,
            event_types=_event_types_from_args(args),
            trace_id=args.trace_id,
            severity=args.severity,
            error_code=args.error_code,
            limit=args.last,
        )
        print(json.dumps([row.to_dict() for row in rows], indent=2))
    elif args.cmd == "report" and args.report_cmd == "savings":
        print(json.dumps(savings_report(args.state_dir, args.tenant), indent=2))
    elif args.cmd == "report" and args.report_cmd == "dashboard":
        print(json.dumps(dashboard_report(args.state_dir, args.tenant), indent=2))
    elif args.cmd == "report" and args.report_cmd == "routes":
        print(json.dumps(RouteFeedbackStore(args.state_dir).summary(), indent=2))
    elif args.cmd == "report" and args.report_cmd == "impact":
        print(json.dumps(model_impact(load_impact_scenario(args.scenario)), indent=2))
    elif args.cmd == "platform" and args.platform_cmd == "list":
        print(json.dumps([profile.to_dict() for profile in built_in_platform_profiles().values()], indent=2))
    elif args.cmd == "platform" and args.platform_cmd == "matrix":
        matrix = platform_matrix()
        if args.require_live:
            matrix["targets"] = [platform_readiness(row["target"], require_live=True).to_dict() for row in matrix["targets"]]
            matrix["contract_ready_count"] = sum(1 for row in matrix["targets"] if row["contract_ready"])
            matrix["live_ready_count"] = sum(1 for row in matrix["targets"] if row["live_ready"])
        print(json.dumps(matrix, indent=2))
    elif args.cmd == "platform" and args.platform_cmd == "validate":
        result = platform_readiness(args.target, require_live=args.require_live)
        if isinstance(result, list):
            print(json.dumps([row.to_dict() for row in result], indent=2))
        else:
            print(json.dumps(result.to_dict(), indent=2))
    elif args.cmd == "conformance" and args.conformance_cmd == "ai":
        print(json.dumps(ai_gateway_conformance(args.state_dir).to_dict(), indent=2))
    elif args.cmd == "conformance" and args.conformance_cmd == "adapters":
        adapters = built_in_adapters()
        if args.adapter:
            print(json.dumps(adapter_conformance(args.adapter, adapters[args.adapter]).to_dict(), indent=2))
        else:
            print(json.dumps([adapter_conformance(name, adapter).to_dict() for name, adapter in adapters.items()], indent=2))
    elif args.cmd == "conformance" and args.conformance_cmd == "plugins":
        if args.plugin_package:
            print(json.dumps(plugin_package_conformance(args.plugin_package).to_dict(), indent=2))
        elif args.all_packages:
            print(json.dumps([plugin_package_conformance(path).to_dict() for path in discover_plugin_packages("plugins")], indent=2))
        else:
            raise SystemExit("use --package or --all-packages")
    elif args.cmd == "policy" and args.policy_cmd == "validate":
        bundle = load_policy_bundle(args.path)
        validate_policy_bundle(bundle)
        print(json.dumps({"valid": True, "policy_bundle_id": bundle.get("metadata", {}).get("name", "policy_bundle")}, indent=2))
    elif args.cmd == "policy" and args.policy_cmd == "publish":
        print(json.dumps(PolicyBundleStore(args.state_dir).publish(args.path, args.actor), indent=2))
    elif args.cmd == "policy" and args.policy_cmd == "list":
        print(json.dumps(PolicyBundleStore(args.state_dir).list(), indent=2))
    elif args.cmd == "policy" and args.policy_cmd == "active":
        print(json.dumps(PolicyBundleStore(args.state_dir).active(args.name), indent=2))
    elif args.cmd == "policy" and args.policy_cmd == "reload":
        print(json.dumps(PolicyBundleStore(args.state_dir).reload(args.name, args.actor), indent=2))
    elif args.cmd == "policy" and args.policy_cmd == "rollback":
        print(json.dumps(PolicyBundleStore(args.state_dir).rollback(args.name, args.version, args.actor), indent=2))
    elif args.cmd == "approval" and args.approval_cmd == "issue":
        record = ApprovalStore(args.state_dir).issue(
            tenant=args.tenant,
            actor=args.actor,
            contract=args.contract,
            policy_bundle_id=args.policy_bundle_id,
            reason=args.reason,
            work_unit_id=args.work_unit_id,
            ttl_seconds=args.ttl_seconds,
        )
        default_ledger(args.state_dir).append(
            LedgerEvent(
                "approval.issued",
                record.tenant,
                work_unit_id=record.work_unit_id,
                policy_bundle_id=record.policy_bundle_id,
                actor=record.actor,
                decision=record.contract,
                details={"approval_id": record.approval_id, "expires_at": record.expires_at, "reason": record.reason},
            )
        )
        print(json.dumps(record.to_dict(), indent=2))
    elif args.cmd == "approval" and args.approval_cmd == "list":
        print(json.dumps([record.to_dict() for record in ApprovalStore(args.state_dir).list(args.tenant)], indent=2))
    elif args.cmd == "approval" and args.approval_cmd == "get":
        print(json.dumps(ApprovalStore(args.state_dir).get(args.approval_id).to_dict(), indent=2))
    elif args.cmd == "plugin" and args.plugin_cmd == "register":
        descriptor = json.loads(Path(args.descriptor_json).read_text(encoding="utf-8")) if Path(args.descriptor_json).exists() else json.loads(args.descriptor_json)
        print(json.dumps(PluginRegistry(args.state_dir).register(descriptor, args.actor), indent=2))
    elif args.cmd == "plugin" and args.plugin_cmd == "list":
        print(json.dumps(PluginRegistry(args.state_dir).list(), indent=2))
    elif args.cmd == "plugin" and args.plugin_cmd == "conformance":
        adapters = built_in_adapters()
        if args.plugin_package:
            print(json.dumps(plugin_package_conformance(args.plugin_package).to_dict(), indent=2))
        elif args.all_packages:
            print(json.dumps([plugin_package_conformance(path).to_dict() for path in discover_plugin_packages("plugins")], indent=2))
        elif args.adapter:
            print(json.dumps(adapter_conformance(args.adapter, adapters[args.adapter]).to_dict(), indent=2))
        else:
            print(json.dumps([adapter_conformance(name, adapter).to_dict() for name, adapter in adapters.items()], indent=2))
    elif args.cmd == "kms" and args.kms_cmd == "create-key":
        print(json.dumps(LocalKMS(args.state_dir).create_key(args.purpose).to_dict(), indent=2))
    elif args.cmd == "kms" and args.kms_cmd == "encrypt":
        print(json.dumps(LocalKMS(args.state_dir).encrypt(args.key_id, args.text.encode("utf-8")), indent=2))
    elif args.cmd == "kms" and args.kms_cmd == "decrypt":
        envelope = json.loads(Path(args.envelope_json).read_text(encoding="utf-8")) if Path(args.envelope_json).exists() else json.loads(args.envelope_json)
        print(LocalKMS(args.state_dir).decrypt(envelope).decode("utf-8"))
    elif args.cmd == "dr" and args.dr_cmd == "export":
        print(json.dumps(export_state(args.state_dir, args.output), indent=2))
    elif args.cmd == "dr" and args.dr_cmd == "import":
        print(json.dumps(import_state(args.archive, args.state_dir, args.replace), indent=2))
    elif args.cmd == "admin" and args.admin_cmd == "readiness":
        state_dir = args.state_dir if args.use_state_dir else None
        print(json.dumps(production_readiness_check(state_dir).to_dict(), indent=2))
    elif args.cmd == "gateway" and args.gateway_cmd == "ai":
        provider = _gateway_provider(args.provider)
        if args.once_json:
            request = json.loads(Path(args.once_json).read_text(encoding="utf-8")) if Path(args.once_json).exists() else json.loads(args.once_json)
            print(json.dumps(handle_chat_completion(request, state_dir=args.state_dir, provider=provider), indent=2))
        elif args.serve:
            _serve_ai_gateway(args.listen, args.state_dir, provider)
        else:
            request = {
                "model": "auto",
                "messages": [{"role": "user", "content": "Hello from the URP mock gateway."}],
            }
            print(json.dumps(handle_chat_completion(request, state_dir=args.state_dir, provider=provider), indent=2))
    elif args.cmd == "benchmark" and args.benchmark_cmd == "run":
        print(json.dumps(run_benchmark_suite(args.suite, args.state_dir), indent=2))
    elif args.cmd == "service" and args.service_cmd == "list":
        print(json.dumps([spec.to_dict() for spec in service_specs().values()], indent=2))
    elif args.cmd == "service" and args.service_cmd == "health":
        print(json.dumps(service_health(args.name, args.state_dir), indent=2))
    elif args.cmd == "service" and args.service_cmd == "run":
        serve_service(args.name, args.listen, args.state_dir)
    elif args.cmd == "release" and args.release_cmd == "sign":
        print(json.dumps(write_release_manifest(".", args.output), indent=2))
    elif args.cmd == "release" and args.release_cmd == "verify":
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        result = verify_release_manifest(manifest, args.root, require_signature=args.require_signature)
        print(json.dumps(result, indent=2))
        if not result["passed"]:
            raise SystemExit(1)
    elif args.cmd == "release" and args.release_cmd == "metadata":
        print(json.dumps(write_package_metadata(args.root), indent=2))


def _payload_from_args(args: argparse.Namespace) -> Any:
    if getattr(args, "file", None):
        return Path(args.file).read_bytes()
    return args.input


def _add_work_unit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--kind", required=True)
    parser.add_argument("--tenant", default="local")
    parser.add_argument("--logical-ref", default="cli://input")
    parser.add_argument("--input", default="")
    parser.add_argument("--file", default=None)
    parser.add_argument("--contract", default=None)


def _work_unit_from_args(args: argparse.Namespace) -> WorkUnit:
    logical_ref = args.logical_ref
    if getattr(args, "file", None) and logical_ref == "cli://input":
        logical_ref = str(Path(args.file).resolve())
    return WorkUnit(
        kind=WorkUnitKind(args.kind),
        tenant=args.tenant,
        logical_ref=logical_ref,
        payload=_payload_from_args(args),
        requested_contract=Contract(args.contract) if args.contract else None,
    )


def _parse_byte_range(raw: str) -> tuple[int, int]:
    parts = raw.split(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise SystemExit("--range must use start:end")
    try:
        start = int(parts[0])
        end = int(parts[1])
    except ValueError as exc:
        raise SystemExit("--range start and end must be integers") from exc
    if start < 0 or end < start:
        raise SystemExit("--range must satisfy 0 <= start <= end")
    return start, end


def _event_types_from_args(args: argparse.Namespace) -> list[str] | None:
    values: list[str] = []
    for raw in args.event_type or []:
        values.extend(part.strip() for part in raw.split(",") if part.strip())
    if args.event_types:
        values.extend(part.strip() for part in args.event_types.split(",") if part.strip())
    return values or None


def _gateway_provider(provider_name: str) -> MockProvider | OpenAICompatibleProvider | None:
    if provider_name == "mock":
        return None
    if provider_name in {"openai-compatible", "openai"}:
        return OpenAICompatibleProvider.from_env()
    raise SystemExit("supported AI providers: mock, openai-compatible")


def _serve_ai_gateway(listen: str, state_dir: str, provider: MockProvider | OpenAICompatibleProvider | None = None) -> None:
    host, port_s = listen.rsplit(":", 1)
    server = create_service_server("gateway-ai", host, int(port_s), state_dir, ai_provider=provider)
    print(f"URP AI gateway listening on http://{host}:{port_s}")
    server.serve_forever()


def _active_policy(state_dir: str, work_unit: WorkUnit) -> Dict[str, Any] | None:
    policy_name = work_unit.policy_context.get("policy_bundle_id") or work_unit.policy_context.get("policy_bundle")
    return resolve_active_policy_bundle(state_dir, str(policy_name) if policy_name else None)


if __name__ == "__main__":
    main()
