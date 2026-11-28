# Digitized Naithani Mg2Sn Figure 3

These are estimates read from the published raster figure, not author-supplied data or new physical calculations. Source: Naithani, Müller and de Boor, _J. Phys. Energy_ **4** (2022) 045002, DOI [10.1088/2515-7655/ac7fb8](https://doi.org/10.1088/2515-7655/ac7fb8), [DLR published PDF](https://elib.dlr.de/193456/). Figure 3 is on PDF page 9, printed page 8. The unchanged embedded image is `source-figure3.png` (1351 × 1078 pixels).

- `published-2pb-curves.csv`: 4467 readable pixel centers across 17 two-parabolic-band traces. Adjacent pixel rows are correlated raster samples, not independent observations.
- `published-spb-curves.csv`: 910 bright-green pixel-run centers belonging to the dashed SPB comparison curves. Gaps are the printed dashes or occlusions.
- `experimental-isolated-symbols.csv`: 152 experimental symbols: 131 isolated symbols plus 21 overlapping squares whose outer extents remain identifiable (17 green and 4 magenta in panel b). Symbols touching curves or other symbols are otherwise omitted. This is an incomplete experimental dataset; absence of a sample/panel combination means no unambiguous symbol passed the extraction criteria.
- `digitization-overlay.png`: black dots every fifth retained 2PB pixel; cyan crosses at experimental symbol centers. The SPB CSV can be checked against the uniquely bright-green source marks.
- `digitize-record.json`: source SHA-256, page mapping, native pixel calibration, sample mapping, guide anchors, method and uncertainty.

Panels (a,c) show Seebeck in **µV/K**, with negative n-type values preserved. Panels (b,d) show electrical conductivity in **S/cm**; the `value_si` column multiplies conductivity by **100** to obtain **S/m**, and Seebeck by 10⁻⁶ to obtain V/K. Panel (b) has a broken axis: the lower segment maps 0–1000 S/cm, the upper segment 2000–5000 S/cm. No values are assigned across the break. Temperature is K.

Sample IDs and colors follow the original legend; extrinsic densities follow Table 2 (PDF page 8, printed page 7):

| ID        | Composition              | Color   | Carrier | Extrinsic density (cm⁻³) |
| --------- | ------------------------ | ------- | ------- | -----------------------: |
| n_sc_sb   | Sc0.05Mg2.01Sn0.97Sb0.03 | red     | n       |                  4.57e20 |
| n_sb      | Mg2.06Sn0.97Sb0.03       | blue    | n       |                  3.97e20 |
| n_sc05    | Sc0.05Mg1.95Sn           | magenta | n       |   2.00e18 (paper fitted) |
| n_sc01    | Sc0.01Mg1.99Sn           | green   | n       |   4.00e17 (paper fitted) |
| p_li03    | Li0.03Mg1.97Sn           | olive   | p       |                  2.69e20 |
| p_li02    | Li0.02Mg1.98Sn           | blue    | p       |                  2.45e20 |
| p_li01    | Li0.01Mg1.99Sn           | magenta | p       |                  1.51e20 |
| p_li005   | Li0.005Mg1.995Sn         | green   | p       |   7.20e19 (paper fitted) |
| p_undoped | Mg2Sn                    | orange  | p       |                  4.40e18 |

The extraction uses actual colored run centers near manually supplied guide anchors. The anchors only disambiguate curve pixels from nearby same-color marks: output values are never interpolated from them. Isolated symbol-like components are removed before curve extraction, and neighborhoods broadened by touching symbols are omitted. Isolated experimental symbol coordinates use filled-area centroids, including for triangles; explicitly identified overlapping squares use their outer-edge box centers. The panel (b) low-conductivity magenta `n_sc05` published curve is **unavailable**: its apparent magenta pixels coincide with experimental square edges, and the green curve overpaints the solid stroke. It is excluded from the published-curve CSV. Its four identifiable experimental symbols remain in native conductivity units. No fitting, curve smoothing, data repair, extrapolation, or gap filling is performed. Sparse traces should be compared only over their retained temperature ranges. Short gaps must not be treated as model discontinuities.

Coordinate envelopes are conservatively ±2 native pixels, approximately ±1.65–1.83 K, ±0.92 µV/K in (a), ±1.92 µV/K in (c), ±19.48 S/cm on (b) upper, ±19.23 S/cm on (b) lower, and ±18.26 S/cm in (d). These include raster localization and approximate tick calibration; they are **digitization envelopes**, not statistical standard deviations or experimental measurement uncertainties. Overlap can introduce larger errors; inspect the overlay before using individual pixels. The paper's low-doped n-type Seebeck mismatch is visible in the source and must not be corrected by moving points.

To regenerate the native image, overlay and digitized data, install NumPy, Pillow, SciPy and pypdfium2 and run from this directory:

```sh
python digitize.py ../Naithani-2022.pdf
```

The script asserts the embedded-image count, all nine sample identities, and minimum extracted counts. Axes, units, signs, legends, and Table 2 identities were checked against original PDF page images. The final source/overlay pair was visually inspected. Missing and obscured portions remain an explicit limitation.

The orange undoped p-type Seebeck model curve crosses zero at approximately **583 K**, with a figure-reading envelope of about **±8 K** near this shallow crossing. Original native-column stroke centers change sign between x=449 and 450 (S=0 at y=912). Negative-Seebeck portions are retained: the plot extends below the zero calibration tick. This is a model-curve crossing; the experimental squares cross earlier.
