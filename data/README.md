# User-supplied measurement test data

These measurements were extracted from `ZEM_data.xlsx` without model fitting or sample selection.
Some samples intentionally cannot be described by the current SPB/DPB models. A failed or poor fit is
a valid program test outcome; these files are not golden fitted parameters or physical acceptance targets.

- [SKD](SKD/): 18 samples, source sheet `SKD GIT`.
- [BCSO](BCSO/): 10 samples, separate measurement grids and sparse supplementary Hall-derived n/mobility columns.
- [BSO](BSO/): 18 samples; suffixes `A`, `uA` and `upA` remain distinct.

Units were confirmed by the user: temperature K; alpha/a uV/K; sigma/s S/cm; BCSO r uOhm*cm;
n_int cm^-3; mu_int cm^2/(V*s). The BCSO R1 cell comment says Ohm*cm, conflicting with the
confirmed r unit; exports follow the user's uOhm*cm confirmation and preserve the original values separately.

Fit-ready files use SI: S = alpha * 1e-6 V/K; rho = r * 1e-8 Ohm*m, or rho = 1/(100*sigma) Ohm*m.
No Hall coefficient was synthesized from carrier concentration or mobility. No interpolation,
smoothing, outlier removal, deduplication, sorting or model-dependent adjustment was performed.
Different temperature grids and independently missing n/mobility cells remain separate series.

`ZEM_manifest.json` records the workbook SHA-256, exact source sheet/column/row mapping, units,
conversions, and output files. The original workbook is not modified or copied into the repository.

## Import verification

All 7,700 source measurement values round-trip through the source CSV exports. All 92 SI files load
with the program's `parse_table` without errors. The original temperature order remains in the files.
The loader warns about unsorted temperatures for `BCSO/855/855_see.txt` and `BCSO/857/857_rho.txt`,
and about resistivity magnitude for BSO samples `300uA`, `302uA` and `325uA`. These are retained
unchanged; warnings do not establish fit suitability. No model was fitted during import.
