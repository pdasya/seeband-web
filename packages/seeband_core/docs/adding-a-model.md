# Adding a model

A new model needs one class and one registration. API and client code find models through the registry, so a typical model needs no changes there.

1. **Describe it.** Return a `ModelDescription` from `describe()`. It lists the fit modes, the data each one needs, and each parameter with its unit, range, scales and bounds. Clients build their forms from this.
2. **Calculate curves.** `calculate(CurveRequest)` returns a `CurveResult`, with a curve for each quantity. `band_diagram(BandDiagramRequest)` returns the sketch of its bands, with each curve by name.
3. **Fit.** `fit(FitRequest)` returns a `FitResult` with the fitted parameters.
4. **Register it.** Add `registry.register(model)` to `seeband_core.model_catalog`, and import `registry` from there.

`LinearModel` in `tests/test_model_registry.py` is a small example. It ignores scales and scattering, which a real model handles. The test shows only that a model works through the interface and registry. `GET /api/models` describes what is registered in `model_catalog`, and `apps/api/tests/test_models.py` checks that with a made-up model.

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

- `fit_quality.rmse` compares model values with data: S in µV/K, and ρ and R_H as a percent of the data. A measured value of 0 is an error for a percent, and near a sign change of R_H, tiny values dominate it.
- `fit_quality.curve_rmse` works from a model and any parameters, with or without a fit. It calculates one curve over the range of the data and interpolates it to the measured temperatures. Pass only the points inside the fit range for an RMSE over that range. On one Mac, a call took 29 to 135 ms at the default 200 points, and the error of interpolating stayed at or below 0.03 µV/K from 100 to 800 K, but reached 0.22 µV/K from 5 K with a small gap. `points` trades one for the other.
- With N2/N1 other than 1, a DPB S fit does not match its own curve (D12), so `curve_rmse` shows a large RMSE after a good fit. That is the mismatch the user sees in the curve, until P6.
- `FitResult.parameter_errors` holds standard errors from the last solver run of each stage. It leaves out errors that are not finite, or exactly 0, which means the data do not determine the parameter. Each error holds other stages fixed. In one test, the reported error of SPB A was 0.069 against a real spread of 146, so these are not plain uncertainties.
- `FitResult.at_bounds` names fitted parameters that ended within 1e-6 of a bound, as a share of the bound, or 1e-6 for a bound below 1.

## Known issues

A known error goes in `known_issues.py`. `FitMode.known_issues` and `FitMode.disabled` expose it in descriptions, and `known_issues` on a result lists those that apply to it. See [known issues](known-issues.md).

## Rules

- Do not mutate requests or measurements.
- State units in the description, and in names where the value is a physical quantity.
- Add tests for physical limits, as the `architecture` skill asks for any change to numbers.

## Curves

`FitMode.curve_kinds` lists the curves a mode offers. `unavailable_curves` says why others are missing, as a code that a client shows through i18n, and a kind in neither reports `not_provided`. `relative_curve_kinds` names curves whose size rests on an assumed value.

## Values and scales

Requests and results hold **core units**: the values the calculations take and return. `model_scales` is the only place that converts them, so the API and client do not. Use `core_to_display` and `display_to_core` for what a user sees, `core_range` and `display_range` for a control, and `default_start` for a complete set of start values. A scale must be above 0, and a fraction must be 1/n, which the registry checks.

- A request holds every parameter of its fit mode, including fixed parameters and those of other scattering types.
- A `ParameterSpec` keeps the range of its control and three scales, because the desktop uses different ones. They come from [the table of desktop modes](desktop-modes.md), and `load_desktop_descriptions()` builds the SPB and DPB descriptions from it. A new model can set all three to the same value.
- `fit_bounds` is in core units, before any factor or transform inside a fit. For example, C in acPhDis is multiplied by 300 inside the fit, and m1 is fitted as m1^(3/2). Where the table records `web_fit_bounds`, as for G in D1, those replace the desktop's bounds.
- The control range limits input only. A fit can return a value outside it.

Names and meanings in a description are in English. A client translates by id, and falls back to the English text for a model it has no translation for.
