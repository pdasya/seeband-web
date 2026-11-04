# Adding a model

A new model needs one class and one registration. API and client code find models through the registry, so a typical model needs no changes there.

1. **Describe it.** Return a `ModelDescription` from `describe()`. It lists the fit modes, the data each one needs, and each parameter with its unit, range, scales and bounds. Clients build their forms from this.
2. **Calculate curves.** `calculate(CurveRequest)` returns a `CurveResult`, with a curve for each quantity.
3. **Fit.** `fit(FitRequest)` returns a `FitResult` with the fitted parameters.
4. **Register it.** Call `registry.register(model)` from `seeband_core.model_registry`.

`LinearModel` in `tests/test_model_registry.py` is a complete example, in about 20 lines.

## Rules

- Do not mutate requests or measurements.
- State units in the description, and in names where the value is a physical quantity.
- Add tests for physical limits, as the `architecture` skill asks for any change to numbers.

## Scales

A `ParameterSpec` keeps the range of its control and three scales, because the desktop uses different ones for display, for the start of a fit and for curves. They come from [the table of desktop modes](desktop-modes.md), and `load_desktop_descriptions()` builds the SPB and DPB descriptions from it. A new model can set all three to the same value.

The bounds of a fit are in the units of the fit. Where the table records `web_fit_bounds`, as for G in D1, those replace the desktop's bounds.
