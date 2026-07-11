from __future__ import annotations

import argparse
import json
from .contracts import WorkUnit, WorkUnitKind, Contract
from .planner import plan_work_unit


def main() -> None:
    parser = argparse.ArgumentParser(prog="urp", description="URP reference CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    plan = sub.add_parser("plan")
    plan.add_argument("--kind", required=True)
    plan.add_argument("--tenant", default="local")
    plan.add_argument("--logical-ref", default="cli://input")
    plan.add_argument("--input", default="")
    plan.add_argument("--contract", default=None)

    args = parser.parse_args()

    if args.cmd == "plan":
        wu = WorkUnit(
            kind=WorkUnitKind(args.kind),
            tenant=args.tenant,
            logical_ref=args.logical_ref,
            payload=args.input,
            requested_contract=Contract(args.contract) if args.contract else None,
        )
        print(json.dumps(plan_work_unit(wu).to_dict(), indent=2))


if __name__ == "__main__":
    main()
