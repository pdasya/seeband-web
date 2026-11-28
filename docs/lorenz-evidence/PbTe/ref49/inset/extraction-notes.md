# Pei et al., Nature 2011 SI Fig S3(b) inset extraction

Source: `PEI_SI.pdf`, DOI 10.1038/nature09996, original PDF page 2 (printed page 2). See `metadata.json` for source SHA256, pdfplumber version and axis anchors. The original audit visually checked a crop of the original page; source crops are omitted from this package.

Reproduce:

```
python extract.py /path/to/PEI_SI.pdf
```

`fractions_1K.csv` contains all six traces from 300–850 K in 1 K steps. `fractions_50K.csv` is the compact table. `raw_vertices.csv` preserves the original PDF geometry. Values are plot digitizations, not author-supplied numerical datasets. The six source traces are polylines (only move/line commands), so segment intersection requires no curve approximation. Calibration uses piecewise linear mapping between visually verified labeled major ticks. The 850 K x-coordinate exceeds the trace endpoint by only 0.004 PDF points (~0.03 K), which is clamped to the endpoint and recorded in metadata.

The inset labels explicitly identify the upper group as p_Sigma/p_total and the lower group as sigma_Sigma/sigma_total. Color-to-concentration is inherited from the main Fig S3b: green 1.5e20, blue 2.0e20, red 2.5e20 cm^-3. The inset has no independent color legend. A conservative +/-0.005 absolute reading envelope accounts for line width, coordinate stair steps and calibration; this is not a statistical confidence interval or a measure of model validity. Six decimal places are retained for reproducibility, not scientific precision.

| concentration / cm^-3 | p_Sigma/p_total, 400 K | sigma_Sigma/sigma_total, 400 K | p_Sigma/p_total, 700 K | sigma_Sigma/sigma_total, 700 K |
| --------------------- | ---------------------: | -----------------------------: | ---------------------: | -----------------------------: |
| 1.5e20                |               0.821410 |                       0.438184 |               0.952418 |                       0.830521 |
| 2.0e20                |               0.824609 |                       0.458617 |               0.950276 |                       0.822498 |
| 2.5e20                |               0.825676 |                       0.474744 |               0.947601 |                       0.814479 |

The prose on SI page 3 was independently checked against its original page image. It gives b=mu_L/mu_Sigma ~4 and f_L=p_L/p_total ~77% for 2% Na-doped PbTe at 400 K. Under the stated two-hole-band interpretation, these imply p_Sigma/p_total=1-f_L~0.23 and sigma_Sigma/sigma_total=(1-f_L)/(b*f_L+1-f_L)~0.06949. Those values are incompatible with the inset digitization at 400 K by far more than its reading uncertainty. The prose sample has p~2.4e20 cm^-3 (near the red curve), while the inset covers three concentrations. This small concentration difference cannot be established as the cause from the source. Preserve this as an unresolved internal source inconsistency; do not silently relabel the inset or substitute its complements.

Validation executed: extraction assertions check 297 page curves, six expected inset geometries, line-only commands, monotone x, fraction bounds, and nearest-vertex cross-check at 400/700 K (maximum difference 0.001097). A separate CSV check confirmed six complete 551-point grids and no downward discontinuity exceeding 0.003. No repository files or numerical implementations were changed.
