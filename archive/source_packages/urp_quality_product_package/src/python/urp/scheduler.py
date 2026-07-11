from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduleDecision:
    run_now: bool
    region: str
    reason: str


def schedule(deadline_seconds: int | None, carbon_signal: float | None = None, preferred_region: str = "local") -> ScheduleDecision:
    if deadline_seconds is not None and deadline_seconds < 60:
        return ScheduleDecision(True, preferred_region, "interactive_deadline")
    if carbon_signal is not None and carbon_signal > 0.8:
        return ScheduleDecision(False, preferred_region, "defer_due_to_high_carbon_or_grid_signal")
    return ScheduleDecision(True, preferred_region, "run_within_policy")
