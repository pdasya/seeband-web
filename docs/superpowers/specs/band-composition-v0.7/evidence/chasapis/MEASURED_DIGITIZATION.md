# Measured transport data from Chasapis et al.

`measured_seebeck.csv` contains 39 readings of measured Seebeck markers from
Figure 6(d–f), 13 for each Pb₁₋ₓNaₓSe composition x = 0.01, 0.02, 0.03,
covering 300–900 K. `measured_hall.csv` contains 73 readings of measured Hall
markers from Figure 7(a–c), 24, 24 and 25 respectively, covering approximately
10–850 K. These are estimates digitized from published figures, not original
instrument data. No fitted curves or partial-band predictions are included.

## Source and marker selection

Thomas C. Chasapis et al., _Understanding the role and interplay of heavy hole
and light hole valence bands in the thermoelectric properties of PbSe_.
The supplied 41-page PDF has SHA-256
`f04997ac2120fed0bd13cfe98b211ba3adf39c2c4c73cbb48417d454c48669a6`.
The [source PDF](https://arxiv.org/pdf/1502.01087) contains the original figure bitmaps.
PDF page positions are one-based and match printed page numbers in this copy.
Figure captions are on pages 31–32; Figures 4, 6 and 7 are on pages 36, 38 and 39.

The source captions and surrounding text were read using PDFium text extraction.
Original pages were rendered at 216 dpi and visually inspected. The embedded
figure bitmaps were then extracted without resampling using pypdfium2
`PdfImage.get_bitmap().to_pil()` from the page image objects. Figure 6 has
1458 × 1388 pixels; Figure 7 has 1458 × 1022 pixels. CSV pixel coordinates refer
to those native bitmaps, with the origin at the top left and y increasing down.

For Seebeck, the caption identifies **open black circles as measurements** and
the black continuous curve as the two-band fit. Red and blue curves are the
heavy- and light-hole partial coefficients. Only circle centers in panels d,
e and f were read. Figure 4(a), whose red squares, blue triangles and olive
circles identify x = 0.01, 0.02 and 0.03, was inspected as a separate check.

For Hall, only the red open squares in Figure 7(a), blue open triangles in
7(b), and olive open circles in 7(c) were read. Black continuous curves are
fits and were excluded. The isolated small symbols beside composition labels
are legend keys and were excluded. Triangle positions use the midpoint of
the bounding box, consistent with the plotted marker position. Manual center
readings were checked by superimposing a cross at every recorded center on the
original bitmap and inspecting all panels. Overlaps at low temperature make
those centers less precise than isolated markers.

## Calibration and units

All Figure 6 and Figure 7 axes used here are linear. The CSV preserves the
center coordinate for each reading so the calibration can be repeated.

| Panel | Temperature calibration                 | Observable calibration                      |
| ----- | --------------------------------------- | ------------------------------------------- |
| 6(d)  | T = 300 + (pixel_x − 996) × 600 / 416 K | S = (397 − pixel_y) × 100 / 109.333333 µV/K |
| 6(e)  | Same as 6(d)                            | S = (822 − pixel_y) × 100 / 143.5 µV/K      |
| 6(f)  | Same as 6(d)                            | S = (1254 − pixel_y) × 100 / 149.5 µV/K     |
| 7(a)  | T = (pixel_x − 300) × 900 / 383 K       | R_H = (375 − pixel_y) × 0.02 / 92 cm³/C     |
| 7(b)  | T = (pixel_x − 1050) × 900 / 366 K      | R_H = (376 − pixel_y) × 0.008 / 86 cm³/C    |
| 7(c)  | T = (pixel_x − 300) × 900 / 383 K       | R_H = (869 − pixel_y) × 0.006 / 94 cm³/C    |

Tick anchors: Figure 6 uses the labeled 300 and 900 K ticks; its Seebeck scales
use zero and the labeled 100, 200 and, for panel d, 300 µV/K ticks. Figure 7
uses 0 and 900 K ticks; ordinate tick spacings are 0.02, 0.008 and 0.006 cm³/C
in panels a, b and c. Seebeck markers align with the 300, 350, …, 900 K grid;
temperatures are recorded on that grid. Hall temperatures are retained as
axis-read estimates rounded to 0.1 K; nominal experimental temperatures cannot
be recovered reliably from overlapping markers. S is rounded to 0.1 µV/K and
R_H to 0.00001 cm³/C. Decimal precision supports reproducibility and does not
imply this degree of accuracy. Conversion to SI, if needed: multiply S by
10⁻⁶ for V/K and R_H by 10⁻⁶ for m³/C.

## Uncertainty and source limitations

CSV columns named `*_digitization_uncertainty_*` are conservative absolute
reading estimates, not standard deviations, statistical weights, confidence
intervals or experimental error bars. They allow approximately 2–3 pixels for
center selection, compression artifacts and tick calibration: ±3 K and
±3 µV/K for Seebeck, and ±5 K for Hall. Hall ordinate estimates are ±0.0007,
±0.0003 and ±0.0002 cm³/C for x = 0.01, 0.02 and 0.03. The paper plots no
experimental error bars for these series. Experimental systematic errors and
any discrepancies between figures are additional, unquantified uncertainties.

Figure 4(c) was inspected over its full logarithmic temperature range. Its
left ordinate applies to x = 0.01; the right ordinate applies to x = 0.02 and
x = 0.03. Using one ordinate for all three would give incorrect Hall values.
The low-temperature x = 0.02 series reads approximately 0.0136 cm³/C in
Figure 4(c), versus approximately 0.0144 cm³/C in Figure 7(b), beyond the stated
pixel-reading allowance. The low-temperature red and olive readings agree
approximately across the two figures. Figure 7 is therefore the consistent
ordinate and temperature authority for the Hall CSV; Figure 4 was not blended
into it. Raw author data would be needed to resolve the discrepancy.

The Hall x = 0.03 downturn at the high-temperature end is retained, including
the final two points far below the fitted black curve. There is no extrapolation,
smoothing, interpolation, data rejection based on model agreement or fitting
in this extraction. The available Seebeck plot begins at 300 K; the Hall curves
end around 820–850 K. Neither observable is extended beyond its published markers.

## Validation

A focused Python CSV check verifies 39/73 rows, three compositions, explicit
units, finite positive observables, strictly increasing temperatures within
each series, unique temperatures, source pages and panels, and agreement of
every recorded value with the above pixel calibration after rounding. All checks
passed. Every digitized point was visually checked with an overlaid center cross.
