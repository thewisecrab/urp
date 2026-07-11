"""Optional FastAPI skeleton.

This module avoids importing FastAPI at package import time so the reference
tests can run with only the Python standard library.
"""

from __future__ import annotations

from .contracts import WorkUnit, WorkUnitKind
from .planner import plan_work_unit


def create_app():
    try:
        from fastapi import FastAPI
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Install fastapi to run the API skeleton") from exc

    app = FastAPI(title="Universal Reduction Plane")

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.post("/v1/work-units/plan")
    def plan(payload: dict):
        wu = WorkUnit(
            kind=WorkUnitKind(payload["kind"]),
            tenant=payload["tenant"],
            logical_ref=payload["logical_ref"],
            payload=payload.get("payload"),
        )
        return plan_work_unit(wu).to_dict()

    return app
