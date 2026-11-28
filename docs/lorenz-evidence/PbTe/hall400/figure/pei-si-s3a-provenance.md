# Pei supplementary Figure S3(a): visual digitization

Source: `PEI_SI.pdf`, DOI 10.1038/nature09996, original PDF page 2 (printed page 2), Figure S3(a). SHA-256: `cb11a4dd3add97537ca90be16cd25f92f849ae2e553a0edc8262dc87a0ca6578`.

The source page and legend were visually checked, and page 3 was read for sample identification. Red is x=0.00 (PbTe); green is x=0.15 (PbTe0.85Se0.15), both nominally 2% Na doped. Open circles identify Caltech and open squares SICCAS; neither symbol distinguishes composition. The horizontal axis is logarithmic temperature in K, with decade ticks at 1, 10, 100, and 1000 K. The vertical axis is linear R_H in cm^3/C. Values here are positive Hall coefficients.

Render: local pypdfium2 5.15.2, Pillow 13.0.0; original PDF page index 1 rendered at scale=5 (360 dpi), 2977 by 4210 pixels, then cropped with PIL box (650,2700,1510,3530). The source crop is omitted from this package; render the source PDF with these settings to inspect it. No OCR, model inference, resampling fit, or curve smoothing was used. Source PDF unchanged.

In crop coordinates, plot left x=50 is 1 K and right x=837 is 1000 K. The y=31 top axis corresponds to 0.060 cm^3/C; y=759 bottom corresponds to 0.005 cm^3/C. Calibration:

T = 10^[3 (x-50)/787] K.

R_H = 0.060 - (y-31) * 0.055/728 cm^3/C.

Checks against the plotted intermediate decade ticks give x=312 -> 10.0 K and x=575 -> 100.3 K. The y tick spacing is about 132.4 pixels per 0.01 cm^3/C. Lowest square centers (x=155) map to 2.51 K, consistent with the 2.5 K measurement mentioned in page 3 text.

Manual center readings: red peak near (729,49), with adjacent near-maximum at (719,53); green near-maximum near (734–738,263–266). Reported maxima are deliberately rounded. Red 2.5 K and 25 K squares are approximately (155,506), (417,497); green 2.5 K, 10 K, 25 K squares are (155,595), (312,601), (417,605). Near 50 K squares are red (496,492), green (496,590).

The CSV reports conservative visual digitization bounds, not standard deviations, confidence intervals, or experimental measurement errors. Peak temperature bounds allow the neighboring sampled points and broad maximum; peak Hall bounds allow symbol-center ambiguity and line width. Plateau point Hall bounds of ±0.0003 cm^3/C allow approximately four pixels in y. Temperature bounds allow a few pixels in x, with values rounded for legibility. The source does not show measurement error bars in this panel.

For an approximate plateau description over 2.5–25 K, red lies around 0.0241–0.0248 cm^3/C and green around 0.0166–0.0174 cm^3/C. If a single reference is needed, use the separately identified 2.5 K value rather than silently averaging the slope. The text on page 3 calls R_H constant below 50 K; the graph nevertheless shows the small variations recorded here. The two samples must not be pooled.

Peak divided by the 2.5 K value is about 2.43 (PbTe) and 2.44 (15% Se). Conservative interval arithmetic using the CSV bounds gives about 2.38–2.48 and 2.37–2.51, respectively; these are digitization-only ranges. This normalization does not remove physical model assumptions or establish the experimental uncertainty.

Validation: checked the original rendered page, caption, legend, logarithmic x calibration, linear y ticks, and sample discussion. No repository code or numerical model changed; no test suite is applicable to this data-only extraction.
