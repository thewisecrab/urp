from __future__ import annotations
try:
    from fastapi import FastAPI
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    FastAPI = None
    BaseModel = object

from .contracts import ResourceRef, ResourceContract
from .planner import build_plan
from .ai_router import route_ai_request

if FastAPI:
    app = FastAPI(title="Universal Reduction Plane")

    class PlanRequest(BaseModel):
        logical_id: str
        resource_type: str
        tenant: str = "default"
        content_type: str = "application/octet-stream"
        contract: str = "exact-byte"
        sample: str = ""

    class AIRouteRequest(BaseModel):
        prompt: str
        quality_required: str = "standard"
        latency_budget_ms: int = 2000

    @app.post("/v1/resources/plan")
    def plan(req: PlanRequest):
        resource = ResourceRef(req.logical_id, req.resource_type, req.tenant, req.content_type)
        contract = ResourceContract(mode=req.contract)  # type: ignore[arg-type]
        result = build_plan(resource, contract, req.sample.encode())
        return result.__dict__ | {"resource": resource.__dict__, "contract": contract.__dict__}

    @app.post("/v1/ai/route")
    def ai_route(req: AIRouteRequest):
        return route_ai_request(req.prompt, req.quality_required, req.latency_budget_ms).__dict__
else:
    app = None

if __name__ == "__main__":
    if not FastAPI:
        raise SystemExit("Install fastapi and uvicorn to run the API server")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
