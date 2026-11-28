# Hattori Supplementary Figure S4 digitization

Image-only estimates of panels **d, e, f**, acoustic exponent γ = −0.5, for every published ΔE = −0.5, −0.4, …, +0.5 eV. No transport model was evaluated, fitted or used to guide extraction.

Source is obtained locally as `source.pdf` (not redistributed here); relevant original PDF position is **46**, printed supplement page **9**. `metadata.json` records SHA-256 hashes. The figure is a **1387×779 embedded raster** (`s4-native.png`); high-DPI rendering does not add information. Axes, color legend, caption and neighboring supplementary text were visually inspected. The source has no published uncertainty bars.

## Data

- `raw_trace_pixels.csv`: all 5,654 native-column coordinates for 33 traced curves, including observed RGB at each selected center. Coordinates use the native image, origin at upper left. These preserve the full traced native domains; integer-like staircase behavior is image quantization.
- `digitized_curves.csv`: 1,815 rows on a shared μ = −0.75 to +0.60 eV grid, spacing 0.025 eV; μ = 0 exists for every trace. Columns: `panel,quantity,delta_e_ev,mu_ev,value,lower,upper,unit,status,source_y_px,envelope_lo_y_px,envelope_hi_y_px`.
- `quantity` is `sigma` (S/m), `seebeck` (uV/K) or `kappa_el` (W/(m K)). The original σ axis uses (Ω m)⁻¹ with a 10⁶ multiplier. Values and bounds are absolute, positive values as plotted; no normalization was applied.
- `status=resolved` identifies separated image-space traces. `overlap_unresolved` means the center is a representative of merged ink and **must not be treated as an independently measured curve value**. `near_floor_unresolved` additionally means ink merges with the plot floor. A reported zero center does not establish an exact physical zero.
- `lower,upper` are conservative **image-reading envelopes**, not confidence intervals or experimental errors. They contain ±1.5 vertical pixels plus ±0.5 horizontal pixel times observed local slope, with unions over connected extracted centers within 1.2 vertical pixels. The neutral S trace at x<320 has no independently identifiable ink; its representative center is bracketed by the full local trace band. Palette classification can remain ambiguous inside merged ink.

Calibration uses native tick centers, **not the horizontal plot frames**: σ zero y=363 and 19.625 px per 10⁶ S/m; S zero y=361.5 and 37.5 px per 200 uV/K; κ zero y=358 and 41.5 px per 10 W/(m K). For x, all panels have 123 px/eV; μ=0 is x=143.5, 374.5, 602.5 respectively. Placement uncertainty is covered by the image envelope. No extrapolation beyond native trace columns is performed. Common-grid values use linear interpolation between extracted pixel coordinates; the 0.025 eV step does not imply independent information at that precision.

`trace-overlay.png` superposes small black trace-center markers on the native source crop. `digitized-envelopes.png` shows the absolute curves and reading envelopes. `validation.json` records status coverage and native μ domains. Several curves genuinely overlap or become unobservable at this raster resolution; coverage flags remain part of the data.

## Reproduce

From the parent benchmark directory, download the source and verify the exact bytes before extraction. The SHA-256 is the content pin: an updated PDF from the same URL must fail this check rather than silently replace the reference.

```sh
curl -fL https://arxiv.org/pdf/2603.21649 -o figure/source.pdf
python -m pip install pypdfium2==5.15.2
python - <<'PYCODE'
from pathlib import Path
import hashlib
import pypdfium2 as pdfium
source = Path('figure/source.pdf')
assert hashlib.sha256(source.read_bytes()).hexdigest() == '1131f062bd5dca7915fe01ff72a0f2bba46ba0a836c860cb1ddcaf40535ef971'
pdf = pdfium.PdfDocument(source)
images = [obj for obj in pdf[45].get_objects() if obj.type == 3]
assert len(images) == 1
images[0].extract('figure/s4-native')
PYCODE
python figure/digitize_s4.py
```

The digitizer asserts the source hash, trace count, common-grid row count, μ=0 coverage and envelope containment. It records calibration, palette, continuity settings and manually checked neutral S anchors. Extraction uses RGB white-to-ink ray separation and monotone raster-space tracking; continuity supplies no transport model. It regenerates the local trace overlay and the included independent plot `digitized-envelopes.png`. Ignore rules exclude source images and overlays from this review bundle.
