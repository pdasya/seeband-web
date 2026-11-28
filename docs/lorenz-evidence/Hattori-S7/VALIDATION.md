# S7 validation evidence

Validation performed on 2026-11-27 against core revision `84af5de52675c45ebbc139ec517873c573a4effa`, which was the review checkout HEAD. Python 3.12.7, NumPy 1.26.4, SciPy 1.15.2, pandas 2.2.3, Matplotlib 3.10.0 and Pillow 10.4.0 were used. Commands ran from this directory with the pinned core `src` directory on `PYTHONPATH`; plotting used a writable Matplotlib cache. No production code or physics formulas were changed.

The following commands all exited zero:

```sh
python replay.py
python independent.py
python compare.py figure/s7_beta1_digitized.csv
```

The replay generated 301 gap points and checked recovered μ and κ/(σT)=L. Independent composite Simpson integration checked all 28 normalized predictions at the seven integer gap values. The maximum absolute difference was 3.4167 × 10⁻¹². Halving the integration step and extending the cutoff from 80 to 100 kBT changed dimensionless observables by at most 1.963 × 10⁻¹² relative. The analytic β=1 conductivity identity was also checked by the independent script.

| Quantity      | Readable non-anchor values | Inside graphical bounds | Largest absolute relative center difference |
| ------------- | -------------------------: | ----------------------: | ------------------------------------------: |
| σ/σ₁₀         |                          4 |                       4 |                                      0.125% |
| \|S\|/\|S₁₀\| |                          6 |                       6 |                                      0.124% |
| κ/κ₁₀         |                          6 |                       6 |                                      0.195% |
| L/L₁₀         |                          4 |                       4 |                                      0.192% |

The σ centers and hence L centers at gaps 8 and 9 remain missing; geometric bounds are retained. Gap 10 is a normalization identity and is excluded from the independent graphical counts. These are graphical reading envelopes with shared calibration uncertainty; residual percentages do not certify the source raster's accuracy.

A CSV-by-CSV comparison against the pre-curation exports found maximum scaled numeric changes `abs(new-old)/max(1,abs(old))` of 8.21 × 10⁻¹² for model values and 4.00 × 10⁻¹³ for comparison values. Reading CSVs were copied unchanged. The regenerated comparison plot was visually inspected for labels and occlusion handling.

This pass did not repeat manual source reading or certify the original calibration. Hash-checked source extraction is documented in `figure/README.md`; metadata preserves the original extraction environment. Agreement applies to normalized curves in this symmetric fixed-μ setup, not absolute experimental Lorenz numbers, fitted material parameters, or arbitrary model cases. Scientific-owner confirmation remains separate.
