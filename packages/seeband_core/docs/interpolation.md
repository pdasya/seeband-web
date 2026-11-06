# Interpolation

`interpolation.interpolate` replaces measured data by a polynomial on an even grid, as the desktop's interpolation buttons do.

## Semantics

| Question              | Answer                                                                                                                                                                                                                                        |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Method                | A Chebyshev polynomial of degree 10, fitted to all the data of a quantity, including points outside the fit range                                                                                                                             |
| Grid                  | `int((max - min) / 20)` evenly spaced points from the minimum to the maximum of the fit range. Both ends are included, except with one point, which is the minimum. So the step is about 20 K on wide ranges, and up to 40 K on the narrowest |
| Quantities            | One switch applies to the quantities the fit mode uses, and the desktop has a button per quantity (D23)                                                                                                                                       |
| When it recalculates  | Whenever the fit range or the data change. The API keeps no state, so each request calculates it. On the desktop, the grid stays from the click (D23)                                                                                         |
| Switched off          | The fit reads the measured points inside the range, with `in_fit_range`. D16 on the desktop, where this can break a later fit, is not ported                                                                                                  |
| A range it cannot use | An error: under 20 K, starting at 0 K or below, or over 200000 K. On the desktop, a range under 20 K fails inside the button, which unchecks itself and leaves the data raw (D23)                                                             |

## In the web client

FS3 decided these, which the core leaves open. They are in `apps/web`.

| Question                   | Answer                                                                                                                                                  |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| One quantity failing       | It is named, and a fit cannot read it, while the others stay. Whether that blocks a fit depends on the mode, which FS8 decides                          |
| Flags                      | `extrapolated`, `underdetermined`, and 0 for `measured_points_in_range`, are shown for each quantity. With 0, the text says that every value is made up |
| A value that is not finite | A fit cannot read that quantity, as the API refuses null                                                                                                |
| Switched off               | The measured data were never changed, so they are back at once                                                                                          |

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

## Known issues

**It extrapolates, sometimes badly.** The grid covers the whole fit range even beyond the data, the polynomial makes up those points, and they enter the fit as data. P7 limits the grid to the data, and C14 records it as a known issue. `extrapolated` reports it.

| Case                                                              | Largest made-up value against the data maximum                  |
| ----------------------------------------------------------------- | --------------------------------------------------------------- |
| `01_Fe2VAl09Si01_see`, data 25 to 750 K, range 50 to 800 K        | 0.998 times                                                     |
| `02_SiP`, data from about 300 to 650 K, default range 50 to 800 K | 2.4e4 times in S, 9.2e4 in ρ with negative values, 3.4e4 in R_H |
| `03_AWI32_SI_hall`, range 5 to 240 K, with no data in it          | about 7000 times                                                |

An independent review ran fits on these on one Mac. On `02_SiP` with the default range, SPB S + ρ ends as `failed` with an internal error, and on 100 to 800 K as `converged` with 17 negative points in ρ. The fit code is the desktop's, but the desktop itself was not run on them.

**The polynomial may not be set by the data.** `underdetermined` reports fewer independent points than the 11 coefficients, as in `02_SiP_hall.txt`, with 10 rows. Closely spaced temperatures can still give made-up values without this flag: 15 rows in 5 groups 0.01 K apart reached 743 times the data maximum in the review.

## Comparison with the desktop

`tests/fixtures/interpolation_references.json` holds output from the real functions of the desktop, for all 9 example files on 4 ranges, at SeeBand commit `803b0e7`. Temperatures must match exactly, and values within 1e-9 of the largest value in each case, because single values pass through zero. The largest relative difference on one Mac, on numpy 2.5 against the 1.26 of the references, was 9.3e-11. Running the desktop's real button handlers gave the same output on all 36 cases.

To regenerate it, use a clean SeeBand checkout next to this repository, in an environment outside the repository. Two runs gave byte-identical files with these versions:

```sh
uv venv --python 3.11 ../seeband-tf-env
uv pip install --python ../seeband-tf-env/bin/python numpy==1.26.4
../seeband-tf-env/bin/python packages/seeband_core/scripts/capture_interpolation_references.py \
  --desktop ../SeeBand \
  --output packages/seeband_core/tests/fixtures/interpolation_references.json
```
