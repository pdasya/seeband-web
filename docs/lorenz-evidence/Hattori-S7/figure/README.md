# Supplementary Figure 7: β=1 digitization

The CSV contains all seven plotted gap positions, 4 through 10, for σ, |S| and κₑₗ in the left panel. These are image estimates, not source numerical data. The source is arXiv:2603.21649, PDF page 49 (printed supplementary page 12). The caption, legend, ticks and immediately preceding normalization statement were visually checked against the rendered original page.

The x coordinate is `gap_kbt = Eg/(kBT)`, not chemical potential. At μ=0 each ordinate is normalized by its corresponding value at Eg=10kBT. `abs_S` denotes a magnitude ratio; this figure does not establish the sign of S.

Locally regenerated `source_page49.png` retains the page and caption; source images and overlays are excluded from this bundle. `s7_source_embedded.png` is the unchanged lossless 1387×399 raster extracted from the PDF. `s7_beta1_overlay.png` enlarges that raster 3× with nearest-neighbor sampling and overlays coordinate envelopes and center crosses in the left panel: magenta σ, dark orange |S|, teal κₑₗ. Other panels remain visible for context but have no digitized output.

The native calibration is x=110 at gap4, x=443 at gap10, y=299 at ratio1, y=61 at ratio1.8. Thus gap=4+(x−110)6/333 and ratio=1+(299−y)0.8/238. Bounds are conservative deterministic coordinate envelopes, not statistical confidence intervals or the authors' error bars. Center ±6 native pixels vertically covers an entire ~9–10px glyph plus read/calibration allowance; ±7px is used for partially overlapping glyphs. Horizontal envelopes are ±6px, corresponding to ±0.108108 gap units. These bounds contain shared calibration errors and must not be treated as independent random uncertainties.

The blue σ markers at gaps8 and9 are entirely hidden. Their central ratios are blank (`unavailable_overlap`). Their bounds cover the entire colored overlap cluster plus1px: native y=[286,305] at gap8, giving ratio=[0.979832,1.043697]; y=[292,304] at gap9, giving [0.983193,1.023529]. These are image-geometry envelopes for an obscured coordinate, not measured blue marker centers. At gap10, all central values are1 only because of source normalization; `normalization_anchor_overlap` flags that this is not an independent image measurement.

The straight connecting line segments do not supply additional independently sampled data. No points outside the plotted gap range were invented. Precision beyond the envelopes is not supported by the source raster.

Reproduce from the parent benchmark directory:

```sh
python -m pip install pypdfium2==5.15.2 pillow==10.4.0
curl -fL https://arxiv.org/pdf/2603.21649 -o figure/source.pdf
python figure/digitize_s7.py figure/source.pdf
```

The digitizer verifies SHA-256 `1131f062bd5dca7915fe01ff72a0f2bba46ba0a836c860cb1ddcaf40535ef971` before extraction. This hash pins the source bytes even if the URL is updated. It asserts the raster dimensions, 21 rows, exactly two missing centers and containment of all finite centers. It regenerates the source page, raster and overlay locally; ignore rules exclude them from the review bundle. `metadata.json` preserves original extraction tool versions, calibration, coordinates and exclusions. These bounds are not experimental uncertainty.
