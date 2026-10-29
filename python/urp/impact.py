from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping


class ImpactModelError(ValueError):
    """Raised when an impact scenario is incomplete or internally inconsistent."""


_INPUT_PRICING_MODES = {"list_price", "effective_blended"}
_ATTRIBUTION = "gross_attributional_constant_demand"


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
    input_pricing: str | None = None
    provider_cache_read_share: float | None = None
    provider_cache_write_share: float | None = None
    cache_read_price_ratio: float | None = None
    cache_write_premium: float | None = None
    energy_kwh_fixed_per_avoided_call: float | None = None
    energy_kwh_per_token: float | None = None

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
            input_pricing=_input_pricing(payload),
            provider_cache_read_share=_optional_number(payload, "provider_cache_read_share"),
            provider_cache_write_share=_optional_number(payload, "provider_cache_write_share"),
            cache_read_price_ratio=_optional_number(payload, "cache_read_price_ratio"),
            cache_write_premium=_optional_number(payload, "cache_write_premium"),
            energy_kwh_fixed_per_avoided_call=_optional_number(payload, "energy_kwh_fixed_per_avoided_call"),
            energy_kwh_per_token=_optional_number(payload, "energy_kwh_per_token"),
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
        if self.input_pricing is None:
            raise ImpactModelError(
                "input_pricing is required. "
                "Use 'list_price' only when you intend to price avoided input tokens at the full input list rate "
                "(this can overstate savings if the provider would have billed prompt-cache reads below list price). "
                "Use 'effective_blended' with provider_cache_read_share and cache_read_price_ratio when those shares are known. "
                "URP does not choose a rate for you."
            )
        if self.input_pricing not in _INPUT_PRICING_MODES:
            raise ImpactModelError("input_pricing must be list_price or effective_blended")
        for field_name in ("provider_cache_read_share", "provider_cache_write_share"):
            value = getattr(self, field_name)
            if value is not None and not 0 <= value <= 1:
                raise ImpactModelError(f"{field_name} must be between 0 and 1")
        read_share = self.provider_cache_read_share or 0.0
        write_share = self.provider_cache_write_share or 0.0
        if read_share + write_share > 1:
            raise ImpactModelError("provider cache read share plus write share cannot exceed 1")
        for field_name in ("cache_read_price_ratio", "cache_write_premium"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ImpactModelError(f"{field_name} must be non-negative")
        cache_fields_set = any(
            value is not None
            for value in (
                self.provider_cache_read_share,
                self.provider_cache_write_share,
                self.cache_read_price_ratio,
                self.cache_write_premium,
            )
        )
        if self.input_pricing == "list_price" and cache_fields_set:
            raise ImpactModelError(
                "cache pricing fields require input_pricing='effective_blended'; "
                "list_price is the backward-compatible full-rate path and does not apply them"
            )
        if self.input_pricing == "effective_blended":
            if self.provider_cache_read_share is None or self.cache_read_price_ratio is None:
                raise ImpactModelError(
                    "effective_blended pricing requires provider_cache_read_share and cache_read_price_ratio"
                )
            write_supplied = self.provider_cache_write_share is not None
            premium_supplied = self.cache_write_premium is not None
            if write_supplied != premium_supplied:
                raise ImpactModelError(
                    "provider_cache_write_share and cache_write_premium must be supplied together; "
                    "URP does not assume a write share or a write premium"
                )
        if self.energy_kwh_per_avoided_model_call is not None and self.energy_kwh_per_avoided_model_call < 0:
            raise ImpactModelError("energy_kwh_per_avoided_model_call must be non-negative")
        fixed_supplied = self.energy_kwh_fixed_per_avoided_call is not None
        token_supplied = self.energy_kwh_per_token is not None
        if fixed_supplied != token_supplied:
            raise ImpactModelError(
                "energy_kwh_fixed_per_avoided_call and energy_kwh_per_token must be supplied together; "
                "URP does not assume either term is zero"
            )
        if self.energy_kwh_per_avoided_model_call is not None and fixed_supplied:
            raise ImpactModelError(
                "provide either energy_kwh_per_avoided_model_call or the fixed-plus-per-token model, not both"
            )
        if self.energy_kwh_fixed_per_avoided_call is not None and self.energy_kwh_fixed_per_avoided_call < 0:
            raise ImpactModelError("energy_kwh_fixed_per_avoided_call must be non-negative")
        if self.energy_kwh_per_token is not None and self.energy_kwh_per_token < 0:
            raise ImpactModelError("energy_kwh_per_token must be non-negative")
        if self.grid_kg_co2e_per_kwh is not None and self.grid_kg_co2e_per_kwh < 0:
            raise ImpactModelError("grid_kg_co2e_per_kwh must be non-negative")
        if self.grid_kg_co2e_per_kwh is not None and not _has_energy_model(self):
            raise ImpactModelError(
                "grid_kg_co2e_per_kwh requires energy_kwh_per_avoided_model_call "
                "or both energy_kwh_fixed_per_avoided_call and energy_kwh_per_token"
            )


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
    pricing = _input_price(row)
    effective_input_price = pricing["effective_input_cost_per_million_tokens"]
    baseline_ai_cost = (
        baseline_input_tokens / 1_000_000 * effective_input_price
        + baseline_output_tokens / 1_000_000 * row.ai_output_cost_per_million_tokens
    )
    ai_cost_avoided = (
        total_input_tokens_avoided / 1_000_000 * effective_input_price
        + cached_output_tokens_avoided / 1_000_000 * row.ai_output_cost_per_million_tokens
    )

    baseline_direct_cost = baseline_storage_cost + baseline_transfer_cost + baseline_ai_cost
    gross_monthly_savings = storage_cost_avoided + transfer_cost_avoided + ai_cost_avoided
    net_monthly_savings = gross_monthly_savings - row.monthly_urp_operating_cost
    horizon_net_value = net_monthly_savings * row.analysis_horizon_months - row.implementation_cost
    payback_months = row.implementation_cost / net_monthly_savings if net_monthly_savings > 0 else None
    roi = horizon_net_value / row.implementation_cost if row.implementation_cost > 0 else None

    avoided_call_tokens = cached_input_tokens_avoided + cached_output_tokens_avoided
    energy = _energy_impact(row, model_calls_avoided, avoided_call_tokens, context_input_tokens_avoided)

    baseline_tokens = baseline_input_tokens + baseline_output_tokens
    avoided_tokens = total_input_tokens_avoided + cached_output_tokens_avoided
    return {
        "model_version": "urp.impact.v1",
        "model_revision": "v1.1-draft",
        "scenario": row.name,
        "currency": row.currency,
        "classification": "modeled_scenario_not_forecast",
        "rebound_adjusted": False,
        "attribution": _ATTRIBUTION,
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
            "demand_assumption": "constant",
        },
        "input_pricing": pricing,
        "financial_impact": {
            "monthly_storage_cost_avoided": _money(storage_cost_avoided),
            "gross_storage_cost_avoided": _money(storage_cost_avoided),
            "monthly_data_transfer_cost_avoided": _money(transfer_cost_avoided),
            "gross_data_transfer_cost_avoided": _money(transfer_cost_avoided),
            "monthly_ai_cost_avoided": _money(ai_cost_avoided),
            "gross_ai_cost_avoided": _money(ai_cost_avoided),
            "gross_monthly_savings": _money(gross_monthly_savings),
            "monthly_urp_operating_cost": _money(row.monthly_urp_operating_cost),
            "net_monthly_savings": _money(net_monthly_savings),
            "gross_net_of_operating_cost_monthly": _money(net_monthly_savings),
            "annualized_net_savings": _money(net_monthly_savings * 12),
            "gross_direct_cost_reduction_rate": _ratio(gross_monthly_savings, baseline_direct_cost),
            "implementation_cost": _money(row.implementation_cost),
            "payback_months": round(payback_months, 2) if payback_months is not None else None,
            "analysis_horizon_months": row.analysis_horizon_months,
            "horizon_net_value": _money(horizon_net_value),
            "horizon_roi": round(roi, 4) if roi is not None else None,
            "rebound_adjusted": False,
            "net_monthly_savings_meaning": (
                "Same value as gross_net_of_operating_cost_monthly: gross avoided direct cost minus the "
                "supplied URP operating cost, at constant demand. It is not a change in total spend, "
                "not net of rebound, and not an accounting opinion."
            ),
            "gross_net_of_operating_cost_monthly_meaning": (
                "Gross avoided direct cost minus the supplied URP operating cost, at constant demand. "
                "It is not a change in total spend if usage grows, and it is not rebound-adjusted."
            ),
        },
        "environmental_impact": energy,
        "boundaries": [
            "Rates are operator assumptions, not measured production outcomes.",
            "Avoided cost, energy, and CO2e are gross and attributional at constant demand. They are not net of rebound.",
            "Exact cache and context reduction are modeled; semantic cache, model routing, and training savings are excluded.",
            "input_pricing is required. list_price is an explicit full-rate choice and can overstate savings when a provider would have billed prompt-cache reads below list price.",
            "effective_blended input pricing applies the operator-supplied cache-read share, cache-read price ratio, and optional cache-write premium to avoided calls and context reductions. It does not model extra writes caused by editing a cached prefix.",
            "Request fees, taxes, discounts other than the explicit cache ratios, cache storage, and workload growth are excluded unless represented in operating cost.",
            "gross_net_of_operating_cost_monthly (also exposed as net_monthly_savings) subtracts the supplied URP operating cost. It is not a change in total spend and is not rebound-adjusted.",
        ],
    }


def rebound_indicator(actual_absolute_reduction: float, expected_gross_reduction: float) -> Dict[str, Any]:
    """Compute R = 1 - (actual absolute reduction / expected gross reduction).

    Both inputs are caller-supplied totals. This helper does not observe a
    deployment and does not claim a measured rebound.
    """
    if isinstance(actual_absolute_reduction, bool) or isinstance(expected_gross_reduction, bool):
        raise ImpactModelError("rebound indicator inputs must be numeric")
    try:
        actual = float(actual_absolute_reduction)
        expected = float(expected_gross_reduction)
    except (TypeError, ValueError) as exc:
        raise ImpactModelError("rebound indicator inputs must be numeric") from exc
    if not math.isfinite(actual) or not math.isfinite(expected):
        raise ImpactModelError("rebound indicator inputs must be finite")
    if expected <= 0:
        raise ImpactModelError("expected_gross_reduction must be positive")
    indicator = 1.0 - (actual / expected)
    return {
        "R": round(indicator, 6),
        "definition": "R = 1 - (actual_absolute_reduction / expected_gross_reduction)",
        "rebound_adjusted": False,
        "measured": False,
        "note": (
            "Indicator only. R=0 means the absolute reduction matched the gross estimate; "
            "R=1 means no absolute reduction; R>1 means absolute consumption increased. "
            "Not a measured Jevons rebound."
        ),
    }


def _input_price(row: ImpactScenario) -> Dict[str, Any]:
    if row.input_pricing == "list_price":
        return {
            "mode": "list_price",
            "cache_discount_applied": False,
            "backward_compatible_list_price": True,
            "effective_input_price_ratio": 1.0,
            "effective_input_cost_per_million_tokens": row.ai_input_cost_per_million_tokens,
            "note": (
                "Avoided input tokens are priced at the full input list rate because input_pricing is list_price. "
                "This can overstate savings when the provider would have billed prompt-cache reads below list price. "
                "Use effective_blended with an operator-supplied cache-read share and price ratio when those are known."
            ),
        }
    read_share = float(row.provider_cache_read_share)
    read_ratio = float(row.cache_read_price_ratio)
    write_share = float(row.provider_cache_write_share or 0.0)
    write_premium = float(row.cache_write_premium) if row.cache_write_premium is not None else None
    uncached_share = 1.0 - read_share - write_share
    ratio = uncached_share * 1.0 + read_share * read_ratio
    if write_premium is not None:
        ratio += write_share * write_premium
    return {
        "mode": "effective_blended",
        "cache_discount_applied": True,
        "backward_compatible_list_price": False,
        "provider_cache_read_share": read_share,
        "cache_read_price_ratio": read_ratio,
        "provider_cache_write_share": write_share if row.provider_cache_write_share is not None else None,
        "cache_write_premium": write_premium,
        "cache_write_premium_applied": write_premium is not None,
        "uncached_input_share": round(uncached_share, 6),
        "effective_input_price_ratio": round(ratio, 6),
        "effective_input_cost_per_million_tokens": row.ai_input_cost_per_million_tokens * ratio,
        "note": (
            "Avoided calls and context-compiler input tokens are priced at the blended effective input rate. "
            "The blend is operator-supplied. It is still gross and attributional at constant demand, "
            "and it does not add a penalty for prefix-cache invalidation."
        ),
    }


def _energy_impact(
    row: ImpactScenario,
    model_calls_avoided: float,
    avoided_call_tokens: float,
    context_input_tokens_avoided: float,
) -> Dict[str, Any]:
    if not _has_energy_model(row):
        return {
            "estimated": False,
            "rebound_adjusted": False,
            "attribution": _ATTRIBUTION,
            "reason": (
                "Provide measured energy_kwh_per_avoided_model_call, or both "
                "energy_kwh_fixed_per_avoided_call and energy_kwh_per_token. "
                "URP does not assume a universal inference energy value."
            ),
        }
    if row.energy_kwh_fixed_per_avoided_call is not None and row.energy_kwh_per_token is not None:
        monthly_kwh_avoided = (
            model_calls_avoided * row.energy_kwh_fixed_per_avoided_call
            + (avoided_call_tokens + context_input_tokens_avoided) * row.energy_kwh_per_token
        )
        method = (
            "gross attributional, constant demand: E = E_fixed * avoided exact-cache calls "
            "+ E_token * avoided tokens. Context-only reductions include token energy and not the fixed per-call term. "
            "Both intensities are operator-supplied. Not net of rebound."
        )
        model_name = "fixed_plus_per_token"
    else:
        monthly_kwh_avoided = model_calls_avoided * float(row.energy_kwh_per_avoided_model_call)
        method = (
            "gross attributional, constant demand: avoided exact-cache model calls multiplied by "
            "operator-supplied measured energy per call. Context-token reductions are not included. Not net of rebound."
        )
        model_name = "per_call"
    energy: Dict[str, Any] = {
        "estimated": True,
        "rebound_adjusted": False,
        "attribution": _ATTRIBUTION,
        "model": model_name,
        "monthly_kwh_avoided": _metric(monthly_kwh_avoided),
        "gross_monthly_kwh_avoided": _metric(monthly_kwh_avoided),
        "annual_kwh_avoided": _metric(monthly_kwh_avoided * 12),
        "gross_annual_kwh_avoided": _metric(monthly_kwh_avoided * 12),
        "method": method,
    }
    if row.grid_kg_co2e_per_kwh is not None:
        monthly_co2 = monthly_kwh_avoided * row.grid_kg_co2e_per_kwh
        energy["monthly_kg_co2e_avoided"] = _metric(monthly_co2)
        energy["gross_monthly_kg_co2e_avoided"] = _metric(monthly_co2)
        energy["annual_kg_co2e_avoided"] = _metric(monthly_co2 * 12)
        energy["gross_annual_kg_co2e_avoided"] = _metric(monthly_co2 * 12)
    return energy


def _has_energy_model(row: ImpactScenario) -> bool:
    return row.energy_kwh_per_avoided_model_call is not None or (
        row.energy_kwh_fixed_per_avoided_call is not None and row.energy_kwh_per_token is not None
    )


def _input_pricing(payload: Mapping[str, Any]) -> str:
    if "input_pricing" not in payload or payload["input_pricing"] is None:
        raise ImpactModelError(
            "input_pricing is required. "
            "Use 'list_price' only as an explicit full-rate choice, or 'effective_blended' with cache shares. "
            "Omitting it no longer selects the full list rate."
        )
    value = payload["input_pricing"]
    if not isinstance(value, str):
        raise ImpactModelError("input_pricing must be list_price or effective_blended")
    return value


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
