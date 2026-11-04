# Adding a model

A new model needs one class and one registration. API and client code find models through the registry, so a typical model needs no changes there.

1. **Describe it.** Return a `ModelDescription` from `describe()`. It lists the fit modes, the data each one needs, and each parameter with its unit, range, scales and bounds. Clients build their forms from this.
2. **Calculate curves.** `calculate(CurveRequest)` returns a `CurveResult`, with a curve for each quantity.
3. **Fit.** `fit(FitRequest)` returns a `FitResult` with the fitted parameters.
4. **Register it.** Call `registry.register(model)` from `seeband_core.model_registry`.

`LinearModel` in `tests/test_model_registry.py` is a small example. It ignores scales and scattering, which a real model handles. API and client code do not exist yet, so the test shows only that a model works through the interface and registry.

Register at import of a module that every process imports. A fit runs in a separate process, and one started with `spawn` holds only what its imports registered, while one started with `fork` also inherits what the parent registered, so a mistake can show on only one platform.

## Rules

- Do not mutate requests or measurements.
- State units in the description, and in names where the value is a physical quantity.
- Add tests for physical limits, as the `architecture` skill asks for any change to numbers.

## Values and scales

Requests and results hold **core units**: the values the calculations take and return. `model_scales` is the only place that converts them, so the API and client do not. Use `core_to_display` and `display_to_core` for what a user sees, and `default_start` for a complete set of start values.

- A request holds every parameter of its fit mode, including fixed parameters and those of other scattering types.
- A `ParameterSpec` keeps the range of its control and three scales, because the desktop uses different ones. They come from [the table of desktop modes](desktop-modes.md), and `load_desktop_descriptions()` builds the SPB and DPB descriptions from it. A new model can set all three to the same value.
- `fit_bounds` is in core units, before any factor or transform inside a fit. For example, C in acPhDis is multiplied by 300 inside the fit, and m1 is fitted as m1^(3/2). Where the table records `web_fit_bounds`, as for G in D1, those replace the desktop's bounds.
- The control range limits input only. A fit can return a value outside it.

Names and meanings in a description are in English. A client translates by id, and falls back to the English text for a model it has no translation for.
