# Absolute resistivity of 2 atom% Na-doped PbTe at 400 K

**Result: rho(400 K) ≈ 0.57 mΩ cm = 5.7 × 10^-6 Ω m.** A conservative visual digitization interval is 0.54–0.60 mΩ cm. This interval describes reading uncertainty, not experimental error bars or a statistical confidence interval.

Primary source: Y. Pei et al., “Convergence of electronic bands for high performance bulk thermoelectrics,” Nature 473, 66–69 (2011), DOI [10.1038/nature09996](https://doi.org/10.1038/nature09996), Figure 3(a). [Publisher figure page](https://www.nature.com/articles/nature09996/figures/3). The publisher caption identifies 2 atom% Na doping for the composition series. The inspected graph legend identifies filled blue squares as resistivity for x = 0.00 in PbTe_(1−x)Se_x; open blue squares are Seebeck coefficient. The right-hand axis is rho in mΩ cm; the left-hand axis is S and must not be used for rho. The solid green model curve is for x = 0.15, so it was not used.

The original audit inspected the 946 × 374 pixel publisher image and its caption. The image and publisher HTML are omitted; download the image below and consult the publisher figure page. Download URL:
https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fnature09996/MediaObjects/41586_2011_Article_BFnature09996_Fig3_HTML.jpg
Image SHA-256: 25b95f06f53abf7a0e6b0ba4921a86a24aad29c4c0e4318831c6820700689638.

## Visual extraction

Pixel coordinates refer to the original downloaded image, origin at upper left. The x axis is linear: 300 K at x≈94 and 900 K at x≈427, so 400 K maps to x≈149.5. The filled blue square there has visible blue edges at approximately x=145–154, y=260–264; its center is approximately (149.5,261.5). Part of the symbol is covered by the red downward triangle for x=0.15. The blue square position, rather than the red symbol or black circle, is used.

The right-hand rho ticks are approximately y=271.5 for 0.5 mΩ cm and y=68 for 2.0 mΩ cm. Linear calibration gives rho = 0.5 + (271.5−y) × 1.5/203.5 mΩ cm. At y=261.5 this is 0.574 mΩ cm, deliberately rounded to 0.57. The interval allows about four pixels of vertical reading ambiguity and symbol overlap. No interpolation in temperature, transport-model inference, curve fit, or smoothing was used. The original audit used enlarged crops for inspection; these are omitted here. Quantitative coordinates refer to the unchanged source image.

## Sample correspondence and limits

Fetch the supplement from [Caltech's author repository](https://authors.library.caltech.edu/records/r4cjr-qn161/files/nature09996-s1.pdf). Its SHA-256 is cb11a4dd3add97537ca90be16cd25f92f849ae2e553a0edc8262dc87a0ca6578. Original PDF page 3 (printed page 3), section 2, explicitly analyzes 2% Na-doped PbTe at 400 K, gives its low-temperature inferred hole density as approximately 2.4×10^20 cm^-3, and refers to combining its partial hole densities with measured resistivity. Render page 3 locally to verify the source; its page image is omitted here.

This establishes correspondence at the published sample/composition level between the main Figure 3 x=0 series and the supplement's PbTe analysis. Neither cited source supplies a specimen identifier proving that every plotted transport datum was taken from the identical physical pellet. Do not silently substitute the x=0.15 alloy or its 2.5×10^20 cm^-3 model concentration. This extraction supplies absolute rho only; any subsequent band mobility calculation retains its own assumptions about p, f_L, mobility ratio, Hall factors, and electron contribution.

Validation: visually checked original Figure 3 axes, linear scales, legend, filled/open symbols, caption, and original supplement page 3. Recomputed the pixel calibration and mΩ cm to Ω m conversion (1 mΩ cm = 10^-5 Ω m). No repository code or numerical model changed; no test suite applies to this evidence-only extraction. Retrieved 2026-11-27.
