# Golden results

[`tests/fixtures/golden/`](../tests/fixtures/golden) records what the SeeBand desktop application computes for the 3 examples, in all 14 combinations of model, fit mode and scattering. Regression tests in the port compare against these files.

**They record the desktop's behaviour, not correct physics.** Known errors are included on purpose, and many fits are doubtful. The physics fixes change these results later, with a physicist's confirmation. [The summary](golden-results-summary.md), generated from the files, lists every run.

## How they were captured

The script drives the real desktop `MainWindow` without a screen, using Qt's `offscreen` platform:

- It loads the S, ρ and R_H files through the real import handlers, which run the real neural net thread.
- It selects each scattering type in the real combo boxes.
- It runs the body of each real fitting thread and records every call to `fit_module` with its exact arguments, result and error.

Each run uses the default fit range of 50 to 800 K, with interpolation off. Each example starts in a fresh window.

This differs from using the application by hand. No one clicks the buttons, and nothing was checked by eye on a real screen. The script supplies file names in place of the file dialog, and runs fit thread bodies directly rather than as background threads. The window is not shown, has no stylesheet, and does not receive fit results in its labels and plots. From reading the code, none of this changes what a fit receives.

## What each file holds

- `environment`, `source` and `input_files_sha256`: versions, SeeBand commit and hashes of the input files.
- `start_values`: DPB starting values in each window after loading the files. Where a net matches, they equal the neural net references. `02_SiP` matches no net, so it holds the slider defaults.
- `runs`: one entry per combination, with `status`, `printed_error`, `warnings`, and for iterative fits `stopped_by`, `iterations` and `stop_path`. Each also holds:
  - `calls`: the fit and curve calls, with arguments and results. The arguments hold the input data, start values and bounds.
  - `emitted`: what the thread would send to the window: the curve and final parameters.
  - `manual_curve_calls`: the curve calculated from the slider values before the fit.
- `d1_with_g_minimum_1`: the D1 case described below.

The arguments keep the desktop's own order and units, so they match the `fit_module` functions.

## Which combinations run

| Combination                | 01_Fe2VAl09Si01 | 02_SiP | 03_AWI32_SI |
| -------------------------- | --------------- | ------ | ----------- |
| SPB S                      | runs            | runs   | runs        |
| SPB S + ρ, all scattering  | runs            | runs   | runs        |
| SPB S + ρ + R_H, all       | fails           | fails  | fails       |
| DPB S                      | runs            | runs   | runs        |
| DPB S + ρ, all scattering  | runs            | runs   | runs        |
| DPB S + ρ + R_H, `acPh`    | runs            | runs   | runs        |
| DPB S + ρ + R_H, `dis`     | fails           | fails  | fails       |
| DPB S + ρ + R_H, `acPhDis` | runs            | runs   | runs        |

"Runs" means that the application returns a result, not that the result is sound.

- **SPB S + ρ + R_H (D2):** the fit thread stops with `'MainWindow' object has no attribute 'fermi_slider_spb'`, before any fit call. So D3, D6 and D7 could not be observed. D5 is recorded: the slider curve runs before the fit, with C multiplied by 300 twice, in `manual_curve_calls`.
- **DPB S + ρ + R_H with `dis` (D1):** the fit stops with `Initial guess is outside of provided bounds`. With the G slider minimum set to 1, the fit returns a result, but this is not credible on `01` and `02`: see the summary. These runs use G bounds of 1 to 200, so they are not a reference for the web bounds of 0.5 to 2, and no golden result exists for those bounds. The script sets the slider minimum directly. That a lower limit of 0.01 in Advanced options gives the same minimum comes from reading the code.

## Results to treat with caution

- **Most fits are doubtful.** The summary counts the runs where a fitted parameter stops at a bound or does not move.
- **Every `acPhDis` fit stops early (D18).** In both DPB modes on all examples, the loop ends on the check of C and D alone, after 1 or 2 iterations, even though other parameters are still changing.
- **`02_SiP`, DPB:** m_eff comes out as about 4e-07, and in S + ρ + R_H, m₁ reaches its upper bound of 10. No net matches this example, so these fits start from the slider defaults. The logs show division by zero, overflow and a `fsolve` call limit.
- **SPB S + ρ on `01` and `02`:** E_F stops at its lower bound of -3000 K. This window's mass defaults to -1.00, unlike the other SPB windows (D11).

## Regenerating

The script needs a clean SeeBand checkout at commit `803b0e7`, and it stops otherwise. Run this from the repository root, with SeeBand next to this repository. The environment stays outside the repository:

```sh
uv venv --python 3.11 ../seeband-golden-env
uv pip install --python ../seeband-golden-env/bin/python \
  tensorflow==2.15.1 numpy==1.26.4 h5py==3.16.0 scipy==1.17.1 mpmath==1.4.1 PyQt5==5.15.11 pyqtgraph==0.14.0
../seeband-golden-env/bin/python packages/seeband_core/scripts/capture_golden_results.py \
  --desktop ../SeeBand \
  --output packages/seeband_core/tests/fixtures/golden
uv run python packages/seeband_core/scripts/summarize_golden_results.py
```

The files hold exact script output and are excluded from Prettier, so any change to a number shows in the diff. `test_files_are_unchanged` pins their hashes, so a regeneration needs a deliberate update of the pinned values. Repeated runs gave byte-identical files with these versions, on one Mac on Apple Silicon. C5 sets the tolerance for other versions.

## Results on the project's versions

The golden results use Python 3.11, numpy 1.26 and scipy 1.17, while the project uses Python 3.13, numpy 2.5 and scipy 1.18. A one-off replay, not in this repository, ran all 195 recorded calls through the ported modules on the project's versions:

| Result                         | Calls |
| ------------------------------ | ----- |
| Exact match                    | 163   |
| Relative difference below 1e-6 | 20    |
| Relative difference below 1e-3 | 2     |
| Same expected error            | 3     |
| Relative difference above 1e-3 | 7     |

The 7 large differences, of 42 to 100%, are all DPB fits on `02_SiP`: the doubtful fits with m_eff of about 4e-07. The next largest is 1e-4, in the G minimum case on `01`. The modules differ from the desktop only in imports and table loading, so the versions are the likely cause, although this was not tested separately. C5 decides how to treat `02_SiP`.
