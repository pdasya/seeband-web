# Adding a model

A new model needs one class and one registration. API and client code find models through the registry, so a typical model needs no changes there.

1. **Describe it.** Return a `ModelDescription` from `describe()`. It lists the fit modes, the data each one needs, and each parameter with its unit, range, scales and bounds. Clients build their forms from this.
2. **Calculate curves.** `calculate(CurveRequest)` returns a `CurveResult`, with a curve for each quantity.
3. **Fit.** `fit(FitRequest)` returns a `FitResult` with the fitted parameters.
4. **Register it.** Add `registry.register(model)` to `seeband_core.model_catalog`, and import `registry` from there.

`LinearModel` in `tests/test_model_registry.py` is a small example. It ignores scales and scattering, which a real model handles. API and client code do not exist yet, so the test shows only that a model works through the interface and registry.

A fit runs in a separate process, which holds only the models its imports registered, so use `model_catalog` in workers too. `band_models` is the example of a real model.

## Fit outcomes

`fit` returns a `FitResult` with one of four statuses. It raises for an invalid request, for an error in the callback and for `MemoryError`. An invalid request includes empty, non-finite or mismatched measurements, a start value that is not a finite number, inverted bounds, and names a fit cannot use. A start value outside the bounds is `failed`, as D1 records on the desktop.

| Status            | Meaning                                                                                                                              | Parameters                                     |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------- |
| `converged`       | the fit ended normally: an iterative fit met its stop rule, or a single-pass solver returned. This does not mean the result is sound | the result                                     |
| `iteration_limit` | the loop reached its limit. The desktop reports this as success                                                                      | what the fit ended with                        |
| `stopped`         | a callback raised `FitStopped`                                                                                                       | the last iteration, with m1 still at its start |
| `failed`          | the calculation raised. `message` holds fixed text, because solver messages are not written for users                                | the start values                               |

An iterative fit calls `on_iteration` once per iteration, with values in the form of a final result, and `FitMode.iterative` tells a client whether to show a counter. A single-pass fit never calls it. Stopping acts between iterations only, and neither the extra Seebeck stage at the limit nor the Hall stage can be stopped, so a worker still needs a way to end the process.

## Fit quality

- `fit_quality.rmse` compares model values with data: S in µV/K, and ρ and R_H as a percent of the data. `fit_quality.curve_rmse` works from a model and any parameters, with or without a fit, by reading its curve at the measured temperatures.
- `FitResult.parameter_errors` holds standard errors, from the last solver run of each stage, where they are finite. They hold other stages fixed, so a staged fit's real uncertainty is larger.
- `FitResult.at_bounds` names fitted parameters that ended within 1e-6 of the range from a bound.

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
