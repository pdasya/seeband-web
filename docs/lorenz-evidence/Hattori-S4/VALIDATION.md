# S4 validation evidence

Validation performed on 2026-11-27 against core revision `84af5de52675c45ebbc139ec517873c573a4effa`, which was the review checkout HEAD. Python 3.12.7, NumPy 1.26.4, SciPy 1.15.2, pandas 2.2.3, Matplotlib 3.10.0 and Pillow 10.4.0 were used. Commands ran from this directory with the pinned core `src` directory on `PYTHONPATH`; plotting used a writable Matplotlib cache. No production code or physics formulas were changed.

The following commands all exited zero:

```sh
python replay.py
python moments.py
python compare.py
python plot.py
```

The forward replay checks recovered μ to 1e−10 eV and the identity κ/(σT)=L at every point. The resulting `model.csv` contains 3,201 rows. Independent 384-node Gauss–Legendre moments over a ±100 kBT window agreed with the core with maximum relative differences:

| Observable | Maximum relative difference |
| ---------- | --------------------------: |
| σ          |                4.85 × 10⁻¹⁴ |
| S          |                7.25 × 10⁻¹⁴ |
| L          |                1.07 × 10⁻¹³ |
| κ          |                7.81 × 10⁻¹³ |

`comparison.csv` has 2,420 rows (605 points × four quantities). The regenerated readable/in-envelope counts were σ 232/232, S 261/231, κ 356/356 and L 232/232. Median absolute center residuals were 1.42%, 1.43%, 0.65% and 1.70%, respectively. The 30 resolved S discrepancies remain failures of graphical agreement; the evidence is not a blanket agreement claim. All 605 L predictions fall inside the corresponding envelopes, but only 232 have independently resolved centers and 272 have no finite upper bound.

A CSV-by-CSV comparison against the pre-curation exports found maximum scaled numeric changes `abs(new-old)/max(1,abs(old))` of 1.34 × 10⁻¹⁴ for model values and 2.35 × 10⁻¹² for comparison values, consistent with floating-point replay differences. Reading CSVs were copied unchanged.

The regenerated overview plot was visually inspected for labels, bounds and missing-center handling. This pass did not repeat manual source tracing or certify the original calibration; source extraction and digitization assertions are available in `figure/README.md`. The ±10 kBT calculation remains a cutoff sensitivity diagnostic, not a correction to source or core. Graphical envelopes are correlated reading bounds, not statistical confidence intervals. Scientific-owner confirmation remains separate from this computational cross-check.
