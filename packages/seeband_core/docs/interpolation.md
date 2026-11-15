# Interpolation

`interpolation.interpolate` evaluates a degree-10 Chebyshev polynomial only within the overlap of the requested fit range and the measured range of each quantity. P7 (#86) prevents extrapolated points from entering a fit as if they were measured data. The source measurements remain unchanged.

## Semantics

| Question              | Answer                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Method                | A Chebyshev polynomial of degree 10, fitted to all the data of a quantity, including points outside the fit range                                                                                                                                                                                                                                                                                                                       |
| Grid                  | For each quantity, low = max(fit minimum, measured minimum), high = min(fit maximum, measured maximum). Use `int((high - low) / 20)` evenly spaced points on that overlap. Both ends are included except with one point, which is low. The polynomial and step rule are unchanged.                                                                                                                                                      |
| Quantities            | One switch applies to the quantities the fit mode uses, and the desktop has a button per quantity (D23)                                                                                                                                                                                                                                                                                                                                 |
| When it recalculates  | Whenever the fit range or the data change. The API keeps no state, so each request calculates it. On the desktop, the grid stays from the click (D23)                                                                                                                                                                                                                                                                                   |
| Switched off          | The fit reads the measured points inside the range, with `in_fit_range`. D16 on the desktop, where this can break a later fit, is not ported                                                                                                                                                                                                                                                                                            |
| A range it cannot use | Validate the original request first: finite, positive, increasing and at least 20 K, with at most 10000 grid points. Then require at least 20 K of measured overlap, and 40 K where the data narrow the range, as 20 to 40 K gives a grid of one point. Each failure has a reason: `no_overlap`, `overlap_too_short` or `fit_failed`, which the API returns in `interpolation_failure_reasons`; a different quantity can still succeed. |

## In the web client

FS3 decided these, which the core leaves open. They are in `apps/web`.

| Question                   | Answer                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| One quantity failing       | It is named, and a fit cannot read it, while the others stay. Whether that blocks a fit depends on the mode, which FS8 decides                                                                                                                                                                                                                                                                                                             |
| Flags                      | `range_limited` shows when a requested fit range exceeds measured coverage, with the range a fit uses, which results and exports name too. `underdetermined` still warns about the polynomial. With no measured point in the window, every value comes from the polynomial alone, which the warning says whether the window lies between measurements or beyond them. Legacy/client-declared `extrapolated` values remain visibly flagged. |
| A value that is not finite | A fit cannot read that quantity, as the API refuses null                                                                                                                                                                                                                                                                                                                                                                                   |
| Switched off               | The measured data were never changed, so they are back at once                                                                                                                                                                                                                                                                                                                                                                             |

Left for later tasks, and not to be lost:

- **What charts show (FS6).** The desktop shows interpolated points in place of raw ones. The plan for the web is to plot the measured points, and fit the interpolated ones.
- **Neural net (FS9).** The desktop reads raw data for start values, even with interpolation on. Keep that.
- **RMSE (FS6, FS10).** Compare with the data the fit read, and say which.
- **Few points (FS8).** A fit on very few points can still return `converged`, for example on the one point of the narrowest grid.

## Differences from the desktop, for V1

- **One switch rather than one button per quantity (D23).** A user cannot interpolate S and leave ρ measured, so a comparison with the desktop needs all or none.
- **It follows the fit range and data.** The desktop's grid stays from the click (D23), so a comparison must click again after changing the range.
- **A range it cannot use is an error shown to the user.** The desktop's button unchecks itself, and leaves the data raw (D23).
- **A quantity that fails is named,** and a fit cannot read it. The desktop keeps it raw, and says nothing.
- **A new file stays interpolated.** Loading a file on the desktop resets that quantity to raw data while its button stays checked. Here the switch stays on, and the new file is interpolated.
- **All loaded quantities, for now.** The table above says that the switch applies to the quantities the fit mode uses. Until FS4 has a mode, it covers every loaded quantity, and FS8 reads only those of the mode.

## P7 support limit and remaining issues

Successful new interpolation always has `extrapolated = false`. `range_limited` is true if either requested boundary extends beyond that quantity's measured coverage. For S measured from 25 to 750 K and a requested fit range of 50 to 800 K, the result contains 35 points from 50 to 750 K. Different quantities keep their own intersections; their grids need not be identical.

`measured_points_in_range` counts actual input points in the requested range. It may be zero for a supported interior window between sparse measurements. Those values are interpolated rather than extrapolated, but the polynomial can be as far off there as beyond the data: with the rows of `01_Fe2VAl09Si01_see` between 200 and 650 K removed, a 185 to 665 K window gives S from −88.3 to +268.9 µV/K, a change of sign, where the full data give −121.5 to −53.3. No flag reports a gap inside the data; a measure of support and its threshold need a physicist's decision.

The `interpolation_extrapolates` known-issue flag remains for callers explicitly declaring legacy/external extrapolated data. P7 does not remove that provenance warning, but the server no longer produces extrapolated interpolation grids.

**Historical behavior, preserved in the desktop captures:** the former full-fit grid invented the following out-of-support values. These are not the new web results:

| Case                                                              | Largest made-up value against the data maximum                  |
| ----------------------------------------------------------------- | --------------------------------------------------------------- |
| `01_Fe2VAl09Si01_see`, data 25 to 750 K, range 50 to 800 K        | 0.998 times                                                     |
| `02_SiP`, data from about 300 to 650 K, default range 50 to 800 K | 2.4e4 times in S, 9.2e4 in ρ with negative values, 3.4e4 in R_H |
| `03_AWI32_SI_hall`, range 5 to 240 K, with no data in it          | about 7000 times                                                |

An independent review ran fits on those historical extrapolated inputs on one Mac. On `02_SiP` with the default range, SPB S + ρ ends as `failed` with an internal error, and on 100 to 800 K as `converged` with 17 negative points in ρ. The fit code is the desktop's, but the desktop itself was not run on them.

**The polynomial may not be set by the data.** `underdetermined` reports fewer independent points than the 11 coefficients, as in `02_SiP_hall.txt`, with 10 rows. Closely spaced temperatures can still give made-up values without this flag: 15 rows in 5 groups 0.01 K apart reached 743 times the data maximum in the review.

## Comparison with the desktop

The original `interpolation_references.json` remains unchanged as desktop evidence. P7 expectations in `tests/fixtures/physics/p7.json` record changed grids/results and explicit failure cases separately. Cases whose requested range lies entirely within measured coverage retain their desktop results. The regression fixture is generated by the web implementation; separate boundary and polynomial-identity tests check the domain contract. An independent least-squares fit in the Legendre basis, at 100 digits, matched its full-rank cases to 7.7e-15. Its three underdetermined cases, from `02_SiP_hall.txt` with 10 temperatures, pin numpy's minimum-norm choice only: other bases fit the data as exactly and differ by up to 14 % on the grid, so those values are not evidence. Regenerate it with `PYTHONPATH=packages/seeband_core/src uv run python packages/seeband_core/scripts/capture_p7_results.py`.

The support restriction does not bound polynomial values, cure overshoot/conditioning, add independent observations or establish a physically valid fit. No degree, fit weights, bounds or sample values were tuned for this change. Human physicist confirmation and parity (#71) remain separate gates.

`tests/fixtures/interpolation_references.json` holds output from the real functions of the desktop, for all 9 example files on 4 ranges, at SeeBand commit `803b0e7`. For unchanged cases, temperatures must match exactly, and values within 1e-9 of the largest value in each case, because single values pass through zero. The largest relative difference on one Mac, on numpy 2.5 against the 1.26 of the references, was 9.3e-11. Running the desktop's real button handlers gave the same output on all 36 cases.

To regenerate it, use a clean SeeBand checkout next to this repository, in an environment outside the repository. Two runs gave byte-identical files with these versions:

```sh
uv venv --python 3.11 ../seeband-tf-env
uv pip install --python ../seeband-tf-env/bin/python numpy==1.26.4
../seeband-tf-env/bin/python packages/seeband_core/scripts/capture_interpolation_references.py \
  --desktop ../SeeBand \
  --output packages/seeband_core/tests/fixtures/interpolation_references.json
```
