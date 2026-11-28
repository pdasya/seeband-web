# ruff: noqa: T201 -- print replay results for reviewers.
"""Extract SI Fig S3b inset polylines, PDF page 2 (one based).
Run with Python containing pdfplumber; no source PDF modification.
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

import pdfplumber

SOURCE = Path(sys.argv[1])
OUT = Path(__file__).resolve().parent
# Major ticks visually verified against inset_crop.png; top-origin PDF points.
X_TICKS = [
    (300, 402.0602112),
    (400, 415.0208893),
    (500, 428.1017914),
    (600, 440.9422455),
    (700, 453.9029236),
    (800, 466.8636017),
    (900, 479.8242798),
]
Y_TICKS = [
    (0.3, 629.4655914),
    (0.4, 618.2460175),
    (0.5, 607.0862732),
    (0.6, 595.8666992),
    (0.7, 584.5274963),
    (0.8, 573.3677368),
    (0.9, 562.1481781),
    (1.0, 550.9286041),
]
TRACES = [
    (290, "green", 1.5e20, "p_sigma_over_p_total"),
    (291, "blue", 2e20, "p_sigma_over_p_total"),
    (292, "red", 2.5e20, "p_sigma_over_p_total"),
    (293, "green", 1.5e20, "sigma_sigma_over_sigma_total"),
    (294, "blue", 2e20, "sigma_sigma_over_sigma_total"),
    (295, "red", 2.5e20, "sigma_sigma_over_sigma_total"),
]


def interp(x, points):
    points = sorted(points)
    for (a, u), (b, v) in zip(points, points[1:], strict=False):
        if a <= x <= b:
            return u + (v - u) * (x - a) / (b - a)
    raise ValueError(("outside calibration", x))


def path_y(x, pts):
    # 850 K is 0.004 PDF point beyond the plotted endpoint owing to rounding.
    assert pts[0][0] - 0.01 <= x <= pts[-1][0] + 0.01
    x = min(max(x, pts[0][0]), pts[-1][0])
    ys = []
    for (a, u), (b, v) in zip(pts, pts[1:], strict=False):
        assert b >= a, "trace must be monotone in x"
        if a <= x <= b:
            ys.extend([u, v] if a == b else [u + (v - u) * (x - a) / (b - a)])
    assert ys
    return (min(ys) + max(ys)) / 2


with pdfplumber.open(SOURCE) as pdf:
    page = pdf.pages[1]
    assert len(page.curves) == 297
    rows = []
    raw = []
    nearest_errors = []
    for index, color, concentration, quantity in TRACES:
        curve = page.curves[index]
        assert all(item[0] in ("m", "l") for item in curve["path"])
        pts = curve["pts"]
        assert 402 < curve["x0"] < 403 and 473 < curve["x1"] < 474
        for n, (x, y) in enumerate(pts):
            raw.append([index, color, concentration, quantity, n, x, y])
        for temperature_k in range(300, 851):
            x = interp(temperature_k, X_TICKS)
            y = path_y(x, pts)
            fraction = interp(y, [(y, f) for f, y in Y_TICKS])
            assert 0.3 <= fraction <= 1
            rows.append(
                [temperature_k, concentration, color, quantity, f"{fraction:.6f}", index, "0.005"]
            )
            if temperature_k in (400, 700):
                nearest = min(pts, key=lambda p: abs(p[0] - x))
                check = interp(nearest[1], [(y, f) for f, y in Y_TICKS])
                nearest_errors.append(abs(check - fraction))
    assert max(nearest_errors) < 0.003

for name, header, data in [
    (
        "fractions_1K.csv",
        [
            "temperature_k",
            "concentration_cm3",
            "color",
            "quantity",
            "fraction",
            "pdf_curve_index_zero_based",
            "visual_reading_uncertainty_absolute",
        ],
        rows,
    ),
    (
        "raw_vertices.csv",
        [
            "pdf_curve_index_zero_based",
            "color",
            "concentration_cm3",
            "quantity",
            "vertex_index",
            "x_pdf_pt",
            "top_pdf_pt",
        ],
        raw,
    ),
    (
        "fractions_50K.csv",
        [
            "temperature_k",
            "concentration_cm3",
            "color",
            "quantity",
            "fraction",
            "pdf_curve_index_zero_based",
            "visual_reading_uncertainty_absolute",
        ],
        [r for r in rows if r[0] % 50 == 0],
    ),
]:
    with (OUT / name).open("w") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(data)
metadata = {
    "source": str(SOURCE),
    "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "pdfplumber_version": pdfplumber.__version__,
    "pdf_page_one_based": 2,
    "figure": "Fig S3(b) inset",
    "x_ticks_temperature_k_pdf_pt": X_TICKS,
    "y_ticks_fraction_pdf_top_pt": Y_TICKS,
    "method": "Direct PDF polyline vertices; piecewise linear calibration between labeled major ticks; linear segment intersection; midpoint for vertical segments. No smoothing or extrapolation except endpoint clamping within 0.01 PDF point.",  # noqa: E501
    "uncertainty": "Conservative +/-0.005 absolute visual reading envelope, not statistical or model uncertainty. Stroke width 0.318975 PDF pt gives about +/-0.00142 fraction; coordinate quantization/stair steps and tick geometry contribute additional uncertainty.",  # noqa: E501
    "concentration_mapping": "Color inherited from main Fig S3b: green=1.5e20, blue=2.0e20, red=2.5e20 cm^-3; inset itself has no separate color legend.",  # noqa: E501
    "max_nearest_vertex_crosscheck_difference": max(nearest_errors),
    "source_prose_comparison_400K": {
        "page": 3,
        "f_L": 0.77,
        "b": 4,
        "implied_p_sigma_fraction": 1 - 0.77,
        "implied_sigma_sigma_fraction": (1 - 0.77) / (4 * 0.77 + 1 - 0.77),
        "note": "Prose is for 2% Na-doped PbTe. Figure density fractions around .81 conflict with implied .23. Do not silently reinterpret or invert the inset labels.",  # noqa: E501
    },
}
(OUT / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
for r in rows:
    if r[0] in (400, 700):
        print(*r, sep=",")
print(
    "PASS:",
    len(rows),
    "samples;",
    len(raw),
    "vertices; nearest-vertex cross-check max",
    max(nearest_errors),
)
