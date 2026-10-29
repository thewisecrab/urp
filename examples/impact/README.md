# URP Impact Scenarios

These scenarios are transparent financial models, not forecasts or production
benchmarks. Edit the JSON inputs to match measured workload telemetry and
contracted rates, then run:

```bash
urp report impact --scenario examples/impact/illustrative-portfolio.json
```

The low, base, and high examples hold workload volume, unit rates, operating
cost, implementation cost, and analysis horizon constant. They vary only the
exact storage, transfer, cache, and context-reduction assumptions.

Each file sets `input_pricing` to `list_price`. That field is required. It
prices avoided input tokens at the full list rate and can overstate savings
when provider prompt-cache reads are cheaper. `effective_blended` is the
alternative and needs operator-supplied cache shares. `net_monthly_savings`
matches `gross_net_of_operating_cost_monthly`: gross avoided cost minus the
supplied operating cost. It is not a change in total spend.

Energy and carbon are intentionally unestimated. Set
`energy_kwh_per_avoided_model_call` only when provider or hardware telemetry can
support it. Set `grid_kg_co2e_per_kwh` only with an appropriate location- and
time-specific factor.

The model excludes semantic cache, model routing, training reduction, request
fees, taxes, negotiated discounts, workload growth, and any cost not supplied
through the scenario. Use it as a decision aid, not an accounting opinion.
