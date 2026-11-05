# Interpolation

`interpolation.interpolate` replaces measured data by a polynomial on an even grid, as the desktop's interpolation buttons do.

## Semantics

| Question             | Answer                                                                                                                                                |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Method               | A Chebyshev polynomial of degree 10, fitted to all the data of a quantity, including points outside the fit range                                     |
| Grid                 | `int((max - min) / 20)` evenly spaced points from the minimum to the maximum of the fit range, including both ends                                    |
| Quantities           | One switch applies to every loaded quantity. The desktop has a button per quantity (D23)                                                              |
| When it recalculates | Whenever the fit range or the data change. The API keeps no state, so each request calculates it. On the desktop, the grid stays from the click (D23) |
| Switched off         | The fit reads the measured points inside the range, with `in_fit_range`. D16 on the desktop, where this can break a later fit, is not ported          |
| Fit range too narrow | A range under 20 K is an error, because the grid would have no points                                                                                 |

A client asks for each quantity separately, and shows the flags of each.

## Known issues

- **It extrapolates.** The grid covers the whole fit range even beyond the data. For S measured from 25 to 750 K with a range up to 800 K, a degree 10 polynomial makes up the last points, and they enter the fit as data. `extrapolated` reports this. P7 limits the grid to the data, and C14 records it as a known issue.
- **A file with 10 or fewer distinct temperatures does not set the polynomial.** `underdetermined` reports this. This covers `02_SiP_hall.txt`, with 9 rows. The result still matches the desktop's.

## Comparison with the desktop

`tests/fixtures/interpolation_references.json` holds output from the real functions of the desktop, for all 9 example files on 4 ranges, at SeeBand commit `803b0e7`. Its temperatures must match exactly, and its values within a relative difference of 1e-9. The largest difference on one Mac, on numpy 2.5 against the 1.26 of the references, was 9.3e-11.

To regenerate it, use a clean SeeBand checkout next to this repository, in an environment outside the repository. Two runs gave byte-identical files with these versions:

```sh
uv venv --python 3.11 ../seeband-tf-env
uv pip install --python ../seeband-tf-env/bin/python numpy==1.26.4
../seeband-tf-env/bin/python packages/seeband_core/scripts/capture_interpolation_references.py \
  --desktop ../SeeBand \
  --output packages/seeband_core/tests/fixtures/interpolation_references.json
```
