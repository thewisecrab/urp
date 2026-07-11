from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping


class ImpactModelError(ValueError):
    """Raised when an impact scenario is incomplete or internally inconsistent."""


@dataclass(frozen=True)
class ImpactScenario:
    name: str
    currency: str
    storage_gib: float
    storage_reduction_rate: float
    storage_cost_per_gib_month: float
    monthly_data_transfer_gib: float
    data_transfer_reduction_rate: float
    data_transfer_cost_per_gib: float
    monthly_ai_requests: int
    average_input_tokens: float
    average_output_tokens: float
    exact_cache_hit_rate: float
    context_compiler_coverage: float
    context_input_reduction_rate: float
    ai_input_cost_per_million_tokens: float
    ai_output_cost_per_million_tokens: float
    monthly_urp_operating_cost: float
    implementation_cost: float
    analysis_horizon_months: int
    energy_kwh_per_avoided_model_call: float | None = None
    grid_kg_co2e_per_kwh: float | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ImpactScenario":
        required = {
            "name",
            "currency",
            "storage_gib",
            "storage_reduction_rate",
            "storage_cost_per_gib_month",
            "monthly_data_transfer_gib",
            "data_transfer_reduction_rate",
            "data_transfer_cost_per_gib",
            "monthly_ai_requests",
            "average_input_tokens",
            "average_output_tokens",
            "exact_cache_hit_rate",
            "context_compiler_coverage",
            "context_input_reduction_rate",
            "ai_input_cost_per_million_tokens",
            "ai_output_cost_per_million_tokens",
            "monthly_urp_operating_cost",
            "implementation_cost",
            "analysis_horizon_months",
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise ImpactModelError(f"impact scenario is missing required fields: {', '.join(missing)}")

        scenario = cls(
            name=str(payload["name"]),
            currency=str(payload["currency"]),
            storage_gib=_number(payload, "storage_gib"),
            storage_reduction_rate=_number(payload, "storage_reduction_rate"),
            storage_cost_per_gib_month=_number(payload, "storage_cost_per_gib_month"),
            monthly_data_transfer_gib=_number(payload, "monthly_data_transfer_gib"),
            data_transfer_reduction_rate=_number(payload, "data_transfer_reduction_rate"),
            data_transfer_cost_per_gib=_number(payload, "data_transfer_cost_per_gib"),
            monthly_ai_requests=_integer(payload, "monthly_ai_requests"),
            average_input_tokens=_number(payload, "average_input_tokens"),
            average_output_tokens=_number(payload, "average_output_tokens"),
            exact_cache_hit_rate=_number(payload, "exact_cache_hit_rate"),
            context_compiler_coverage=_number(payload, "context_compiler_coverage"),
            context_input_reduction_rate=_number(payload, "context_input_reduction_rate"),
            ai_input_cost_per_million_tokens=_number(payload, "ai_input_cost_per_million_tokens"),
            ai_output_cost_per_million_tokens=_number(payload, "ai_output_cost_per_million_tokens"),
            monthly_urp_operating_cost=_number(payload, "monthly_urp_operating_cost"),
            implementation_cost=_number(payload, "implementation_cost"),
            analysis_horizon_months=_integer(payload, "analysis_horizon_months"),
            energy_kwh_per_avoided_model_call=_optional_number(payload, "energy_kwh_per_avoided_model_call"),
            grid_kg_co2e_per_kwh=_optional_number(payload, "grid_kg_co2e_per_kwh"),
        )
        scenario.validate()
        return scenario

    def validate(self) -> None:
        if not self.name.strip():
            raise ImpactModelError("scenario name cannot be empty")
        if not self.currency.strip():
            raise ImpactModelError("currency cannot be empty")
        for field_name in (
            "storage_gib",
            "storage_cost_per_gib_month",
            "monthly_data_transfer_gib",
            "data_transfer_cost_per_gib",
            "average_input_tokens",
            "average_output_tokens",
            "ai_input_cost_per_million_tokens",
            "ai_output_cost_per_million_tokens",
            "monthly_urp_operating_cost",
            "implementation_cost",
        ):
            if getattr(self, field_name) < 0:
                raise ImpactModelError(f"{field_name} must be non-negative")
        for field_name in (
            "storage_reduction_rate",
            "data_transfer_reduction_rate",
            "exact_cache_hit_rate",
            "context_compiler_coverage",
            "context_input_reduction_rate",
        ):
            value = getattr(self, field_name)
            if not 0 <= value <= 1:
                raise ImpactModelError(f"{field_name} must be between 0 and 1")
        if self.monthly_ai_requests < 0:
            raise ImpactModelError("monthly_ai_requests must be non-negative")
        if self.analysis_horizon_months <= 0:
            raise ImpactModelError("analysis_horizon_months must be positive")
        if self.energy_kwh_per_avoided_model_call is not None and self.energy_kwh_per_avoided_model_call < 0:
            raise ImpactModelError("energy_kwh_per_avoided_model_call must be non-negative")
        if self.grid_kg_co2e_per_kwh is not None and self.grid_kg_co2e_per_kwh < 0:
            raise ImpactModelError("grid_kg_co2e_per_kwh must be non-negative")
        if self.grid_kg_co2e_per_kwh is not None and self.energy_kwh_per_avoided_model_call is None:
            raise ImpactModelError("grid_kg_co2e_per_kwh requires energy_kwh_per_avoided_model_call")


def load_impact_scenario(path: str | Path) -> ImpactScenario:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ImpactModelError("impact scenario must be a JSON object")
    return ImpactScenario.from_mapping(payload)


def model_impact(scenario: ImpactScenario | Mapping[str, Any]) -> Dict[str, Any]:
    row = scenario if isinstance(scenario, ImpactScenario) else ImpactScenario.from_mapping(scenario)
    row.validate()

    baseline_storage_cost = row.storage_gib * row.storage_cost_per_gib_month
    storage_gib_avoided = row.storage_gib * row.storage_reduction_rate
    storage_cost_avoided = storage_gib_avoided * row.storage_cost_per_gib_month

    baseline_transfer_cost = row.monthly_data_transfer_gib * row.data_transfer_cost_per_gib
    transfer_gib_avoided = row.monthly_data_transfer_gib * row.data_transfer_reduction_rate
    transfer_cost_avoided = transfer_gib_avoided * row.data_transfer_cost_per_gib

    baseline_input_tokens = row.monthly_ai_requests * row.average_input_tokens
    baseline_output_tokens = row.monthly_ai_requests * row.average_output_tokens
    model_calls_avoided = row.monthly_ai_requests * row.exact_cache_hit_rate
    cached_input_tokens_avoided = model_calls_avoided * row.average_input_tokens
    cached_output_tokens_avoided = model_calls_avoided * row.average_output_tokens
    uncached_requests = row.monthly_ai_requests - model_calls_avoided
    context_input_tokens_avoided = (
        uncached_requests
        * row.context_compiler_coverage
        * row.average_input_tokens
        * row.context_input_reduction_rate
    )
    total_input_tokens_avoided = cached_input_tokens_avoided + context_input_tokens_avoided
    baseline_ai_cost = (
        baseline_input_tokens / 1_000_000 * row.ai_input_cost_per_million_tokens
        + baseline_output_tokens / 1_000_000 * row.ai_output_cost_per_million_tokens
    )
    ai_cost_avoided = (
        total_input_tokens_avoided / 1_000_000 * row.ai_input_cost_per_million_tokens
        + cached_output_tokens_avoided / 1_000_000 * row.ai_output_cost_per_million_tokens
    )

    baseline_direct_cost = baseline_storage_cost + baseline_transfer_cost + baseline_ai_cost
    gross_monthly_savings = storage_cost_avoided + transfer_cost_avoided + ai_cost_avoided
    net_monthly_savings = gross_monthly_savings - row.monthly_urp_operating_cost
    horizon_net_value = net_monthly_savings * row.analysis_horizon_months - row.implementation_cost
    payback_months = row.implementation_cost / net_monthly_savings if net_monthly_savings > 0 else None
    roi = horizon_net_value / row.implementation_cost if row.implementation_cost > 0 else None

    energy: Dict[str, Any]
    if row.energy_kwh_per_avoided_model_call is None:
        energy = {
            "estimated": False,
            "reason": "Provide measured energy_kwh_per_avoided_model_call to estimate energy; URP does not assume a universal inference energy value.",
        }
    else:
        monthly_kwh_avoided = model_calls_avoided * row.energy_kwh_per_avoided_model_call
        energy = {
            "estimated": True,
            "monthly_kwh_avoided": _metric(monthly_kwh_avoided),
            "annual_kwh_avoided": _metric(monthly_kwh_avoided * 12),
            "method": "avoided exact-cache model calls multiplied by operator-supplied measured energy per call",
        }
        if row.grid_kg_co2e_per_kwh is not None:
            energy["monthly_kg_co2e_avoided"] = _metric(monthly_kwh_avoided * row.grid_kg_co2e_per_kwh)
            energy["annual_kg_co2e_avoided"] = _metric(monthly_kwh_avoided * row.grid_kg_co2e_per_kwh * 12)

    baseline_tokens = baseline_input_tokens + baseline_output_tokens
    avoided_tokens = total_input_tokens_avoided + cached_output_tokens_avoided
    return {
        "model_version": "urp.impact.v1",
        "scenario": row.name,
        "currency": row.currency,
        "classification": "modeled_scenario_not_forecast",
        "monthly_baseline": {
            "storage_cost": _money(baseline_storage_cost),
            "data_transfer_cost": _money(baseline_transfer_cost),
            "ai_token_cost": _money(baseline_ai_cost),
            "direct_cost": _money(baseline_direct_cost),
            "ai_requests": row.monthly_ai_requests,
            "input_tokens": _metric(baseline_input_tokens),
            "output_tokens": _metric(baseline_output_tokens),
        },
        "monthly_avoided_work": {
            "storage_gib": _metric(storage_gib_avoided),
            "data_transfer_gib": _metric(transfer_gib_avoided),
            "model_calls": _metric(model_calls_avoided),
            "input_tokens": _metric(total_input_tokens_avoided),
            "output_tokens": _metric(cached_output_tokens_avoided),
            "context_input_tokens": _metric(context_input_tokens_avoided),
            "model_call_avoidance_rate": _ratio(model_calls_avoided, row.monthly_ai_requests),
            "total_token_avoidance_rate": _ratio(avoided_tokens, baseline_tokens),
        },
        "financial_impact": {
            "monthly_storage_cost_avoided": _money(storage_cost_avoided),
            "monthly_data_transfer_cost_avoided": _money(transfer_cost_avoided),
            "monthly_ai_cost_avoided": _money(ai_cost_avoided),
            "gross_monthly_savings": _money(gross_monthly_savings),
            "monthly_urp_operating_cost": _money(row.monthly_urp_operating_cost),
            "net_monthly_savings": _money(net_monthly_savings),
            "annualized_net_savings": _money(net_monthly_savings * 12),
            "gross_direct_cost_reduction_rate": _ratio(gross_monthly_savings, baseline_direct_cost),
            "implementation_cost": _money(row.implementation_cost),
            "payback_months": round(payback_months, 2) if payback_months is not None else None,
            "analysis_horizon_months": row.analysis_horizon_months,
            "horizon_net_value": _money(horizon_net_value),
            "horizon_roi": round(roi, 4) if roi is not None else None,
        },
        "environmental_impact": energy,
        "boundaries": [
            "Rates are operator assumptions, not measured production outcomes.",
            "Exact cache and context reduction are modeled; semantic cache, model routing, and training savings are excluded.",
            "Request fees, taxes, discounts, cache storage, and workload growth are excluded unless represented in operating cost.",
            "Net impact subtracts the supplied URP operating cost and implementation cost but is not an accounting opinion.",
        ],
    }


def _number(payload: Mapping[str, Any], key: str) -> float:
    value = payload[key]
    if isinstance(value, bool):
        raise ImpactModelError(f"{key} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ImpactModelError(f"{key} must be numeric") from exc
    if not math.isfinite(number):
        raise ImpactModelError(f"{key} must be finite")
    return number


def _optional_number(payload: Mapping[str, Any], key: str) -> float | None:
    if key not in payload or payload[key] is None:
        return None
    return _number(payload, key)


def _integer(payload: Mapping[str, Any], key: str) -> int:
    value = payload[key]
    if isinstance(value, bool):
        raise ImpactModelError(f"{key} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ImpactModelError(f"{key} must be an integer") from exc
    if number != value:
        raise ImpactModelError(f"{key} must be an integer")
    return number


def _money(value: float) -> float:
    return round(value, 2)


def _metric(value: float) -> int | float:
    rounded = round(value, 6)
    return int(rounded) if rounded.is_integer() else rounded


def _ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0
