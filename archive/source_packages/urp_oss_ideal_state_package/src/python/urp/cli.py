from __future__ import annotations
import argparse
from .contracts import ResourceRef, ResourceContract
from .planner import build_plan

def main() -> None:
    parser = argparse.ArgumentParser(prog="urp")
    parser.add_argument("logical_id")
    parser.add_argument("--resource-type", default="bytes")
    parser.add_argument("--contract", default="exact-byte")
    parser.add_argument("--sample", default="")
    args = parser.parse_args()
    plan = build_plan(ResourceRef(args.logical_id, args.resource_type), ResourceContract(mode=args.contract), args.sample.encode())
    print(plan)

if __name__ == "__main__":
    main()
