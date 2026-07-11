from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List

from .contracts import new_id, utc_now
from .metrics import GLOBAL_METRICS
from .auth import current_tenant
from .storage import append_json_line, ensure_private_file, file_lock


@dataclass(frozen=True)
class FlexibleJob:
    tenant: str
    kind: str
    deadline_seconds: int | None = None
    estimated_runtime_seconds: int = 0
    carbon_signal: float | None = None
    preferred_region: str = "local"
    policy_context: Dict[str, object] = field(default_factory=dict)
    job_id: str = field(default_factory=lambda: new_id("job"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.tenant.strip() or not self.kind.strip():
            raise ValueError("scheduler jobs require tenant and kind")
        if self.deadline_seconds is not None and self.deadline_seconds < 0:
            raise ValueError("deadline_seconds must be non-negative")
        if self.estimated_runtime_seconds < 0:
            raise ValueError("estimated_runtime_seconds must be non-negative")
        if self.carbon_signal is not None and not 0 <= self.carbon_signal <= 1:
            raise ValueError("carbon_signal must be between 0 and 1")
        if not self.preferred_region.strip():
            raise ValueError("preferred_region is required")

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ScheduleDecision:
    run_now: bool
    region: str
    reason: str
    job_id: str | None = None
    shifted_seconds: int = 0
    deadline_seconds: int | None = None
    run_after_seconds: int = 0
    policy: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


class SchedulerStore:
    def __init__(self, state_dir: str | Path = ".urp") -> None:
        self.path = Path(state_dir) / "scheduler_jobs.jsonl"
        ensure_private_file(self.path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def submit(self, job: FlexibleJob) -> ScheduleDecision:
        decision = schedule_job(job)
        row = {"job": job.to_dict(), "decision": decision.to_dict(), "created_at": utc_now()}
        tenant = current_tenant()
        if tenant and job.tenant != tenant:
            from .errors import tenant_mismatch

            raise tenant_mismatch(tenant, job.tenant)
        append_json_line(self.path, row, lock_path=self.lock_path)
        return decision

    def read(self) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        tenant = current_tenant()
        with file_lock(self.lock_path, exclusive=False):
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        row = json.loads(line)
                        if not tenant or row.get("job", {}).get("tenant") == tenant:
                            rows.append(row)
        return rows


def schedule(deadline_seconds: int | None, carbon_signal: float | None = None, preferred_region: str = "local") -> ScheduleDecision:
    return schedule_job(FlexibleJob("local", "batch_compute_job", deadline_seconds, carbon_signal=carbon_signal, preferred_region=preferred_region))


def schedule_job(job: FlexibleJob) -> ScheduleDecision:
    if job.policy_context.get("force_run_now") is True:
        return _decision(job, True, "policy_force_run_now")
    if job.deadline_seconds is not None and job.deadline_seconds < 60:
        return _decision(job, True, "interactive_deadline")
    if job.carbon_signal is not None and job.carbon_signal > 0.8:
        max_shift = int(job.policy_context.get("max_shift_seconds", 900))
        if max_shift < 0 or max_shift > 86400:
            raise ValueError("max_shift_seconds must be between 0 and 86400")
        if job.deadline_seconds is not None and job.deadline_seconds <= max(120, job.estimated_runtime_seconds + max_shift):
            return _decision(job, True, "deadline_prevents_shift")
        GLOBAL_METRICS.inc("urp_scheduler_jobs_shifted_total")
        return _decision(job, False, "defer_due_to_high_carbon_or_grid_signal", shifted_seconds=max_shift, run_after_seconds=max_shift)
    return _decision(job, True, "run_within_policy")


def _decision(
    job: FlexibleJob,
    run_now: bool,
    reason: str,
    shifted_seconds: int = 0,
    run_after_seconds: int = 0,
) -> ScheduleDecision:
    return ScheduleDecision(
        run_now=run_now,
        region=job.preferred_region,
        reason=reason,
        job_id=job.job_id,
        shifted_seconds=shifted_seconds,
        deadline_seconds=job.deadline_seconds,
        run_after_seconds=run_after_seconds,
        policy=dict(job.policy_context),
    )
