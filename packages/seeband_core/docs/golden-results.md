# Golden results

[`tests/fixtures/golden/`](../tests/fixtures/golden) records what the SeeBand desktop application computes for the 3 examples, in all 14 combinations of model, fit mode and scattering. Regression tests in the port compare against these files.

**They record the desktop's behaviour, not correct physics.** Known errors are included on purpose, and some fits below look doubtful. The physics fixes change these results later, with a physicist's confirmation.

## How they were captured

The script drives the real desktop `MainWindow` without a screen, using Qt's `offscreen` platform:

- It loads the S, ρ and R_H files through the real import handlers, which run the real neural net thread.
- It selects each scattering type in the real combo boxes.
- It runs the body of each real fitting thread and records every call to `fit_module` with its exact arguments, result and error.

Each run uses the default fit range of 50 to 800 K, with interpolation off. No Advanced options are changed, except in the one case described under D1. Each example starts in a fresh window.

This differs from using the application by hand in two ways: no one clicks the buttons, and fit threads run directly rather than as background threads. Nothing was checked by eye on a real screen.

## What each file holds

- `environment`, `source` and `input_files_sha256`: versions, SeeBand commit and hashes of the input files.
- `start_sliders`: DPB slider values after loading the files.
- `runs`: one entry per combination, with `status`, `printed_error`, `stopped_by`, `warnings` and:
  - `calls`: the fit and curve calls, with arguments and results. The arguments hold the input data, start values and bounds.
  - `emitted`: what the thread would send to the window: the curve and final parameters.
  - `manual_curve_calls`: the curve calculated from the slider values before the fit.
- `d1_with_g_minimum_1`: the Advanced options case under D1.

The arguments keep the desktop's own order and units, so they match the `fit_module` functions.

## Which combinations work

| Combination                | 01_Fe2VAl09Si01 | 02_SiP | 03_AWI32_SI |
| -------------------------- | --------------- | ------ | ----------- |
| SPB S                      | works           | works  | works       |
| SPB S + ρ, all scattering  | works           | works  | works       |
| SPB S + ρ + R_H, all       | fails           | fails  | fails       |
| DPB S                      | works           | works  | works       |
| DPB S + ρ, all scattering  | works           | works  | works       |
| DPB S + ρ + R_H, `acPh`    | works           | works  | works       |
| DPB S + ρ + R_H, `dis`     | fails           | fails  | fails       |
| DPB S + ρ + R_H, `acPhDis` | works           | works  | works       |

**The failures, on all 3 examples:**

- **SPB S + ρ + R_H (D2):** `'MainWindow' object has no attribute 'fermi_slider_spb'`. It fails before any calculation, so the problems in D3, D5, D6 and D7 could not be observed.
- **DPB S + ρ + R_H with `dis` (D1):** `Initial guess is outside of provided bounds`. With the G slider minimum set to 1, which a lower limit of 0.01 in Advanced options gives, this combination runs.

All iterative fits that ran stopped by reaching the accuracy threshold. None reached the iteration limit.

## Results to treat with caution

- **`02_SiP`, DPB:** m_eff comes out as 0.0, with the other parameters close to their start values. In S + ρ + R_H, m₁ reaches its upper bound of 10. No net matches this example, so these fits start from the slider defaults. The logs show division by zero, overflow and a `fsolve` call limit.
- **SPB S + ρ on `01` and `02`:** E_F stops at its lower bound of -3000 K. In this window the mass defaults to -1.00, unlike the other SPB windows (D11).
- **SPB S on `03`:** E_F stops at its upper bound of 3000 K.
- **Several `acPh`, `dis` and `acPhDis` fits:** parameters stop at bounds, or stay at their start values. `at-bound` flags in C11 will make this visible to users.

## Regenerating

The script needs a clean SeeBand checkout at commit `803b0e7`, and it stops otherwise. Use a separate environment:

```sh
uv venv --python 3.11 golden-env
uv pip install --python golden-env/bin/python "tensorflow==2.15.*" h5py scipy mpmath PyQt5 pyqtgraph
golden-env/bin/python packages/seeband_core/scripts/capture_golden_results.py \
  --desktop ../SeeBand \
  --output packages/seeband_core/tests/fixtures/golden
```

The files hold exact script output and are excluded from Prettier, so any change to a number shows in the diff. Two complete runs gave byte-identical files with the versions recorded there, on one Mac on Apple Silicon. Results from other versions of numpy and scipy may differ slightly: C5 sets the tolerance for that.
