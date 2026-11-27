# ruff: noqa: T201 -- print replay results for reviewers.
"""Extract original Fig. 6 polyline vertices; no fitting or extrapolation."""

import csv
import ctypes as c
import hashlib
import json
from pathlib import Path

import pypdfium2 as pdfium

OUT = Path(__file__).resolve().parent
import sys  # noqa: E402

SOURCE = Path(sys.argv[1])
doc = pdfium.PdfDocument(SOURCE)
page = doc[7]
paths = list(page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_PATH]))


def points(index):
    obj = paths[index]
    matrix = obj.get_matrix()
    result = []
    for j in range(pdfium.raw.FPDFPath_CountSegments(obj)):
        seg = pdfium.raw.FPDFPath_GetPathSegment(obj, j)
        assert pdfium.raw.FPDFPathSegment_GetType(seg) in (0, 2), "not a polyline"
        x, y = c.c_float(), c.c_float()
        assert pdfium.raw.FPDFPathSegment_GetPoint(seg, c.byref(x), c.byref(y))
        result.append(matrix.on_point(x.value, y.value))
    return result


# Original vector tick center coordinates, verified against page image.
x_ticks = [
    (300 + 100 * k, points(i)[0][0]) for k, i in enumerate([179, 187, 189, 191, 193, 195, 197])
]
y_ticks = [
    (1.5 + 0.1 * k, points(i)[0][1]) for k, i in enumerate([199, 201, 203, 205, 207, 209, 211])
]
x0, x1 = x_ticks[0][1], x_ticks[-1][1]
y0, y1 = y_ticks[0][1], y_ticks[-1][1]


def temp(x):
    return 300 + (x - x0) * 600 / (x1 - x0)


def lorenz(y):
    return 1.5 + (y - y0) * 0.6 / (y1 - y0)


# ±0.001 PDF pt coordinate encoding is below the visual line-width envelope.
coord_error_pt = 0.001
rows = []
metadata = []
for index in range(217, 223):
    obj = paths[index]
    color = ("blue", "black", "red")[(index - 217) % 3]
    density = {"blue": 2.5e20, "black": 2e20, "red": 1.5e20}[color]
    style = "solid" if index < 220 else "dotted"
    width = c.c_float()
    assert pdfium.raw.FPDFPageObj_GetStrokeWidth(obj, c.byref(width))
    # Half printed stroke width: conservative plot-reading envelope, not statistical sigma.
    visual_l_error = (width.value / 2) * 0.6 / (y1 - y0)
    vertices = points(index)
    for knot, (x, y) in enumerate(vertices):
        rows.append(
            dict(
                p_cm3=density,
                style=style,
                color=color,
                vertex=knot,
                temperature_k=temp(x),
                lorenz_1e8_w_ohm_k2=lorenz(y),
                temperature_encoding_bound_k=coord_error_pt * 600 / (x1 - x0),
                temperature_calibration_bound_k=0.1,
                lorenz_encoding_bound_1e8=coord_error_pt * 0.6 / (y1 - y0),
                lorenz_visual_halfwidth_1e8=visual_l_error,
                pdf_x_pt=x,
                pdf_y_pt=y,
                path_index=index,
            )
        )
    assert all(vertices[k][0] < vertices[k + 1][0] for k in range(len(vertices) - 1))
    assert pdfium.raw.FPDFPageObj_GetDashCount(obj) == (0 if style == "solid" else 4)
    metadata.append(
        dict(
            path_index=index,
            color=color,
            p_cm3=density,
            style=style,
            count=len(vertices),
            temperature_range_k=[temp(vertices[0][0]), temp(vertices[-1][0])],
            stroke_width_pt=width.value,
            visual_lorenz_halfwidth_1e8=visual_l_error,
        )
    )
with (OUT / "reference.csv").open("w") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
# Fig 5(c), tick centers -0.4 and -0.2 eV and the exact original marker paths.
ef_x0, ef_x1 = points(133)[0][0], points(141)[0][0]
markers = []
for index, color, density in [(157, "red", 1.5e20), (158, "black", 2e20), (159, "blue", 2.5e20)]:
    x = points(index)[0][0]
    markers.append(
        dict(
            path_index=index,
            color=color,
            p_cm3=density,
            pdf_x_pt=x,
            fermi_level_ev=-0.4 + (x - ef_x0) * 0.2 / (ef_x1 - ef_x0),
        )
    )
assert max(abs(temp(x) - v) for v, x in x_ticks) < 0.1
assert max(abs(lorenz(y) - v) for v, y in y_ticks) < 0.00001
record = dict(
    source=str(SOURCE),
    sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    pdf_page_index=7,
    printed_page="125206-8",
    pdfium_version=str(pdfium.PYPDFIUM_INFO),
    x_ticks=x_ticks,
    y_ticks=y_ticks,
    temperature_tick_max_residual_k=max(abs(temp(x) - v) for v, x in x_ticks),
    curves=metadata,
    fig5c_markers=markers,
    fig5c_energy_ticks=[[-0.4, ef_x0], [-0.2, ef_x1]],
    method="Native vector polyline vertices via PDFium; affine tick calibration; no interpolation or extrapolation.",  # noqa: E501
    uncertainties="Encoding bounds assume 0.001 PDF point precision. X tick centers disagree with a single affine transform by up to 0.084 K; use 0.1 K as temperature calibration envelope. Visual halfwidth is half the printed stroke width mapped to L, a conservative digitization envelope, not measurement sigma or model uncertainty. Native vertices are definitive locations of the published curve centerlines.",  # noqa: E501
    verification="Axes, units, legend/color and density mapping visually checked on original page render. Six paths have strictly increasing x; solid dash count 0 and dotted dash count 4; axis tick residual checks passed.",  # noqa: E501
    caveat="Source curves have piecewise-linear irregularities. Keep native coordinates and values; do not infer greater physical precision. Solid paths end at clipping boundary, and contain no higher-temperature data.",  # noqa: E501
)
(OUT / "digitize-record.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(dict(rows=len(rows), curves=metadata, markers=markers), indent=2))
