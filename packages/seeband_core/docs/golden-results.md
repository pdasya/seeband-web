# Golden results

[`tests/fixtures/golden/`](../tests/fixtures/golden) records what the SeeBand desktop application computes for the 3 examples, in all 14 combinations of model, fit mode and scattering. Regression tests in the port compare against these files, with the intentional [P2 Hall correction](dpb-hall-prefactor.md) recorded in a separate set of web expectations. P3 similarly records corrected acPhDis derived curves in `tests/fixtures/physics/p3.json`; historical desktop captures remain unchanged.

**They record the desktop's behaviour, not correct physics.** Known errors are included on purpose, and many fits are doubtful. The physics fixes change these results later, with a physicist's confirmation. [The summary](golden-results-summary.md), generated from the files, lists every run.

## P6 DPB S-only degeneracy

P6 adds `tests/fixtures/physics/p6.json`: explicitly synthetic nonunit-N
S-only fit/recovery references. Historical desktop N = 1 captures remain
unchanged, and their S-only replay still passes. The independent quadrature
checks in `test_dpb_degeneracy.py` validate the density and transport weights
separately from these model-generated regression expectations. See
[the mass convention and residual investigation](dpb-s-degeneracy.md).

Regenerate from the repository root:

```sh
PYTHONPATH=packages/seeband_core/src uv run python packages/seeband_core/scripts/capture_p6_results.py
```

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
  - `graph_buttons`: the calls made by each button of the mode's real additional graphs window, pressed after the fit.
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
- **Every desktop `acPhDis` fit stops early (D18).** In both DPB modes on all examples, the loop ends on the check of C and D alone, after 1 or 2 iterations, even though other parameters are still changing. P5 corrects this in the web version; historical captures remain unchanged.
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

The files hold exact script output and are excluded from Prettier, so any change to a number shows in the diff. `test_files_are_unchanged` pins their hashes, so a regeneration needs a deliberate update of the pinned values. Repeated runs gave byte-identical files with these versions, on one Mac on Apple Silicon. The regression tests below cover only the project's locked versions.

## Regression tests

`tests/test_golden_regression.py` replays all 390 recorded calls on the code in `band_models`: 306 through the model interface, and the 84 of `get_parabolic_band` through a plain function, on the project's versions: Python 3.13, numpy 2.5 and scipy 1.18. The golden results use Python 3.11, numpy 1.26 and scipy 1.17. Only 159 of the calls have distinct inputs, and 84 are `get_parabolic_band`, which uses no physical constants.

| Calls                             | Rule                                                                         | Difference seen                                           |
| --------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------- |
| All curves and graphs             | relative difference of at most 1e-9                                          | exact on one Mac, within the rule on Linux CI             |
| Fits                              | relative difference of at most 1e-5                                          | up to 1.7e-7 on one Mac, within the rule on Linux CI      |
| SPB S on `02_SiP`                 | relative difference of at most 1e-4                                          | 3.4e-6 on one Mac, 1.8e-5 and 2.8e-5 in two Linux CI runs |
| Failing fits                      | status `failed`, and "bounds" in the text                                    |                                                           |
| Listed DPB fits on `02_SiP` (D19) | band gap and E_F within 1e-5, within bounds, m_eff below 1e-5                | not comparable                                            |
| G minimum case on `01`            | stable parameters within 1e-3; P13 collapsed F/G are diagnostic-only (below) | F/G and resulting rho are not numeric references for P13  |

SPB S on `02_SiP` differs between Linux CI runs of the same fit code, so the 1e-5 rule would make the tests flaky. E_F there falls from 100 to 3.76, with solver warnings.

Fit tolerance is wide enough that a small change can pass in a fit, but the curves catch it. Measured with deliberate changes on one Mac: changing the Boltzmann constant to its 2019 value, a change of 3.5e-7, fails 174 tests.

**`02_SiP` in DPB is not stable (D19).** m_eff collapses towards 0 on every version. In the golden results the ρ stage then stays at its start, with A = 40000, so the ρ curve is about 1e-11 against data of 0.016 to 0.16, although A of about 1e-5 would match the data. On the project's versions, A reached about 1e-5 for `acPh` and `acPhDis` on one Mac, while on Linux CI it did so only for `acPh`. So the result depends on the versions and the machine, and these fits differ from the desktop by up to about 9 orders of magnitude in A. They are checked only as the table shows, and should be treated as unsound.

**Graph calls replay with their recorded values.** The additional graphs pass C and D at other scales than the fit (D20), and those values are not core values. So the replay shows the same calculation, not that a graph from a web fit equals the desktop's.

**Every recorded degeneracy ratio is 1 and every recorded m1 in a carrier concentration is 1,** so the replay cannot check either. `tests/test_band_models.py` checks the calls the adapters make, against a table written there.

**What these tests do not cover:**

- `spb_see_res_hall_fit`: its fit fails in the desktop GUI first (D2). The S + ρ + R_H curve is covered, at slider defaults only.
- `is_accuracy_reached` is covered only through fits.
- Other data, other fit ranges and interpolation.

A test fails if this list of uncovered methods changes. The replay names recorded arguments through the signatures of the core, so a refactor that renames a function or drops an argument updates the test helpers, not the pinned fixtures. The test of `spb_see_res_hall_fit` has no recorded call and names its arguments itself.

## P3 derived-curve correction

`tests/fixtures/physics/p3.json` records corrected acPhDis conductivity, thermal
conductivity and band contributions using the historical desktop inputs. Only
those six changed calculation entry points use the new expectations; fits and
measured curves keep their existing expectations. Two non-finite thermal values
from the inherited extreme-parameter numerical limitation (#105) remain present.
P3 corrects the scattering scale, not that separate numerical limitation.

Regenerate from the repository root:

```sh
PYTHONPATH=packages/seeband_core/src uv run python packages/seeband_core/scripts/capture_p3_results.py
```

## P5 convergence correction

`tests/fixtures/physics/p5.json` records the corrected mixed-scattering DPB
fit results, completed iteration counts and parameter histories, separately
from the original desktop captures. Only the affected DPB fitting entry
points use these corrected expectations. SPB and curve replay expectations
remain unchanged.

All six recorded cases (three examples and two DPB modes) complete three
iterations without reaching their existing budgets. The desktop stopped at
one iteration on `02_SiP` and two on the other examples. The Hall budget of
20 is sufficient for these inputs; this does not guarantee convergence on
other inputs. `02_SiP` still has the collapsed-band limitation (#107) and a
Hall mass at its upper bound, so its fitted parameters remain unreliable.

`p5.json` is captured from this code, so it is a regression baseline. For 01
and 03 its values lie within 1e-6 of the desktop captures, so only the
iteration counts tell P5 from the desktop there. An outer loop written apart
from the core corroborates all six entries, within 3.5e-8 for 01 and 03 and
3.4e-6 in A for 02. The case where stopping early mattered, 03 from C = 2,
D = 0.5, is tested in `test_dpb_convergence.py`.

Regenerate from the repository root:

```sh
PYTHONPATH=packages/seeband_core/src uv run python packages/seeband_core/scripts/capture_p5_results.py
```

See [the convergence contract and scientific limits](dpb-convergence.md).

## P4/P12 SPB Hall correction

`tests/fixtures/physics/p4.json` records corrected Hall arrays for the historical
SPB Hall calculation inputs, plus six explicitly synthetic known-parameter
fits (two mass signs and three scattering mechanisms). The original desktop
files remain unchanged; the desktop has no successful SPB Hall fit reference.
The synthetic fit curves are generated model data, not measurements or
independent physical evidence. Independent quadrature and limiting-factor
tests in `test_spb_hall_physics.py` check the Hall statistics separately.
See [the correction and remaining confirmation gates](spb-hall-fit.md).

Regenerate from the repository root:

```sh
PYTHONPATH=packages/seeband_core/src uv run python packages/seeband_core/scripts/capture_p4_results.py
```

## P8 chemical-potential solver

`tests/fixtures/physics/p8.json` records the checked solver's results and
failures for every historical call. Original desktop, P2, P3, P4 and P5
evidence remains unchanged. Independent desktop replays retain the earlier
P2–P5 corrections, and a separate replay checks the P8 expectations for the
same inputs. These generated expectations are regression evidence,
not independent proof of physics. The dedicated conservation, domain and
order-independence tests check the solver separately. See
[the signed-balance contract and limitations](chemical-potential.md).

Both desktop and P8 fit replays use the named cross-platform rules in the
regression table above. P8 does not impose a tighter rule on an already
unstable fit. SPB S on `02_SiP` keeps its existing relative tolerance of
1e-4; a Linux P8 run differed from the recorded E_F by 2.04e-5.

The listed D19 fits still require convergence, finite band parameters,
the `collapsed_m_eff` warning, a mass magnitude below 1e-5, and band gap
and E_F within their original bounds and relative tolerance of 1e-5.
Their scattering values remain machine dependent. Their iteration counts
must be integers from 1 through the mode's configured budget; single-pass
fits must report no iteration count. Stable fits retain exact recorded
iteration counts. P8 status and message comparisons, curve tolerances and
the original desktop evidence remain unchanged.

## P11 pointwise mixed-scattering weight

`tests/fixtures/physics/p11.json` records the 24 affected historical calls
on core `0.1.3` and pins the unchanged P8 fixture hash. Only total S and
refitted parameters/iteration counts use those generated corrections;
unchanged curve fields, unused parameters, statuses and messages remain
checked against their earlier references. The named cross-platform rules
above are preserved. No original desktop or P8 capture is rewritten.

These snapshots are regression evidence, not independent physical proof.
The example-03 alternate-start test instead uses an independently written
outer iteration; it does not read P11 values as its oracle. See
[the independent reference and example movements](dpb-acphdis-weight.md).

## P13 branch-constrained fitting regressions

Core `0.1.4` records all 24 DPB fit calls in `tests/fixtures/physics/p13.json`.
The public signed initial mass fixes the permitted branch. The snapshot pins
hashes of unchanged P8 and P11 evidence, and original desktop captures remain
unchanged. Regression tests retain their existing numeric tolerances.

Intersections of mass bounds with the selected branch alter optimization
trajectories, including positive-branch fits. Examples 01 and 03 retain their
previous successful statuses. All eight example-02 DPB calls now fail at the
existing function-evaluation limit; seven formerly reported convergence with
collapsed parameters and one failed its bounds check. These failures remain
visible and are not evidence that the general fitting problem (P19) is solved.
See [the P13 equations and independent physical limits](dpb-positive-weights.md).

```sh
PYTHONPATH=packages/seeband_core/src uv run python packages/seeband_core/scripts/capture_p13_results.py
```

The already named unreliable example-01 auxiliary `d1` disorder fit reaches a
collapsed positive mass near 1e-10 after P13. The Mac capture takes four outer
iterations; Linux CI takes five. Its iteration regression checks the existing
Hall-mode budget, not exact platform-specific work counts. Both platforms
retain `collapsed_m_eff` and `hall_dis_no_reference`.

The owner approved an explicitly unsupported diagnostic contract for this
historical case on 2026-11-15, keeping P13 separate from P19. F and G and the
resistivity predicted from those fitted values are not numeric compatibility
references: their differences change observables and cannot be described as
mere parameter nonidentifiability. All other parameter comparisons retain the
existing D1 tolerance 1e-3; exact status/message checks and prior-fixture hashes
remain. Every fitted value must be finite and within its recorded input bounds;
mass must be positive and collapsed, with its active-bound diagnostic and both
known-issue flags. Stable cases and fixed-parameter curve regressions remain
numerically compared.

The complete Linux endpoint is recorded in the regression contract's test
(CI run 43693830497). Both endpoints were evaluated at the original measured
temperatures with NumPy 2.5.4/SciPy 1.18.1 and the existing rho-stage objective:

| Endpoint        |              F |            G | Relative L2 rho residual | rho RMSE (ohm m) |
| --------------- | -------------: | -----------: | -----------------------: | ---------------: |
| Mac P13 capture |    4.272005272 | 199.99999998 |           0.999999999968 |   2.794591978e-6 |
| Linux CI        | 7.991751199e-8 |  1.000550172 |           0.813693910020 |   2.273942474e-6 |

For fixed bands and G, rho_i=q_i/F has the independent least-squares solution
1/F=(q·rho_data)/(q·q). For the Mac bands this gives F=3.999968200e-10 within
the existing bounds, improving its objective. The Mac endpoint therefore
shows optimizer stagnation, while the Linux endpoint approximately optimizes
that amplitude direction. Neither result establishes physical fit validity.
The general numerical defect remains P19 (#176); this diagnostic exception
does not repair it, change the estimator or supply a physical acceptance gate.

## Explicit legacy and verified fitting (P19)

From core0.2.0, historical estimator replays in test_golden_regression.py request
legacy-sequential-v1 explicitly. Desktop/P8/P11/P13 fixtures and their comparison
tolerances are unchanged. These tests establish reproduction of that route,
not agreement of the new default with unreliable historical parameter vectors.
New verified-sequential-v2 tests independently check profiling, final conditional
consistency, public-R bounds/held values and physical limits. New implementation
regressions and measured-input aggregate evidence must be recorded separately.
See [the verified fitting contract](verified-sequential-fit.md).

## Stable Fermi integrals (P14)

P14 evaluates the same unnormalised Fermi–Dirac integrals. It uses the stable
softplus for F₀ and quadrature of the Fermi window for the other supported
orders. The continuous half-order integral replaces the old piecewise
approximation in the density equation. Intrinsic DPB density balance uses
scaled positive densities, preserving the normalized residual and its tolerance.

The scalar tests compare the required orders −½, 0, ½, 1 and 2 against 60-digit
references over a grid spanning reduced potentials from −6000 to 6000.
They use a relative tolerance of 1e-12 for normally representable results,
and separately check the scaled forms in the dilute limit. Raw integrals below
the representable range round to zero. The transport tests check the analytic
dilute limits and finite electronic thermal conductivity from 2 K to 800 K
on representative SPB and DPB cases. At 50 K and a 2000 K DPB gap with E_F
at −100 K, all three legacy scattering paths previously returned NaN. An
additional deterministic sample across the public parameter ranges gave
7425 finite, nonnegative thermal points over 2–800 K. The 315 curve requests
in analytically excluded no-root domains were counted separately.

The P14 overlay, `tests/fixtures/physics/p14.json`, records this implementation's
outputs for the affected replays on the original inputs. The desktop capture
and older physics fixtures remain historical evidence. Regenerate the overlay
from the source checkout with:

```sh
PYTHONPATH=packages/seeband_core/src uv run python packages/seeband_core/scripts/capture_p14_results.py
```

Desktop/web comparison in #71 and a physicist's confirmation remain release
requirements. The overlay measures reproducibility of the corrected numerical
paths.
