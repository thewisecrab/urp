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

Energy and carbon are intentionally unestimated. Set
`energy_kwh_per_avoided_model_call` only when provider or hardware telemetry can
support it. Set `grid_kg_co2e_per_kwh` only with an appropriate location- and
time-specific factor.

The model excludes semantic cache, model routing, training reduction, request
fees, taxes, negotiated discounts, workload growth, and any cost not supplied
through the scenario. Use it as a decision aid, not an accounting opinion.
