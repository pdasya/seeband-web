# ruff: noqa: T201 -- print replay results for reviewers.
"""Native PDF Fig 5 fixed-energy slices compared with Fig 6; no extrapolation."""

import csv
import ctypes as c
import hashlib
import json
import sys
from pathlib import Path

import pypdfium2 as pdfium

SOURCE = Path(sys.argv[1])
OUT = Path(__file__).resolve().parent
page = pdfium.PdfDocument(SOURCE)[7]
paths = list(page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_PATH]))


def points(index):
    obj = paths[index]
    result = []
    for j in range(pdfium.raw.FPDFPath_CountSegments(obj)):
        seg = pdfium.raw.FPDFPath_GetPathSegment(obj, j)
        assert pdfium.raw.FPDFPathSegment_GetType(seg) in (0, 2)
        x, y = c.c_float(), c.c_float()
        assert pdfium.raw.FPDFPathSegment_GetPoint(seg, c.byref(x), c.byref(y))
        result.append(obj.get_matrix().on_point(x.value, y.value))
    return result


def slice_at(index, x):
    p = points(index)
    assert all(a[0] <= b[0] for a, b in zip(p, p[1:], strict=False))
    if not p[0][0] <= x <= p[-1][0]:
        return None
    for (xa, ya), (xb, yb) in zip(p, p[1:], strict=False):
        if xa <= x <= xb and xa < xb:
            return ya + (yb - ya) * (x - xa) / (xb - xa)
    raise AssertionError("No enclosing native segment")


def xy(i):
    return points(i)[0]


c_ex0, c_ex1 = xy(133)[0], xy(141)[0]
b_ex0, b_ex1 = xy(90)[0], xy(98)[0]
c_ly0, c_ly1 = xy(143)[1], xy(147)[1]
b_ly0, b_ly1 = xy(102)[1], xy(108)[1]
f_tx0, f_tx1 = xy(179)[0], xy(197)[0]
f_ly0, f_ly1 = xy(199)[1], xy(211)[1]


def fig6_y(y):
    return None if y is None else 1.5 + (y - f_ly0) * 0.6 / (f_ly1 - f_ly0)


rows = []
for color, marker, density, offset in [
    ("red", 157, 1.5e20, 2),
    ("black", 158, 2e20, 1),
    ("blue", 159, 2.5e20, 0),
]:
    cx = xy(marker)[0]
    energy = -0.4 + (cx - c_ex0) * 0.2 / (c_ex1 - c_ex0)
    bx = b_ex0 + (energy + 0.2) * (b_ex1 - b_ex0) / 0.2
    # c has only endpoint temperatures. b supplies 483 and 667 K.
    for t, panel, solid, dotted, x in [
        (300, "5c", 153, 154, cx),
        (483, "5b", 117, 121, bx),
        (667, "5b", 118, 122, bx),
        (850, "5c", 155, 156, cx),
        (300, "5b", 115, 120, bx),
        (850, "5b", 119, 123, bx),
    ]:
        low, high = (c_ly0, c_ly1) if panel == "5c" else (b_ly0, b_ly1)
        origin, span = (1.5, 1.0) if panel == "5c" else (0.0, 30.0)
        fx = f_tx0 + (t - 300) * (f_tx1 - f_tx0) / 600
        for style, index, findex in [
            ("solid", solid, 217 + offset),
            ("dotted", dotted, 220 + offset),
        ]:
            y = slice_at(index, x)
            val = None if y is None else origin + (y - low) * span / (high - low)
            fpoints = points(findex)
            snapped = abs(fx - fpoints[-1][0]) * 600 / (f_tx1 - f_tx0) < 0.1
            fval = fig6_y(slice_at(findex, fpoints[-1][0] if snapped else fx))
            width = c.c_float()
            assert pdfium.raw.FPDFPageObj_GetStrokeWidth(paths[index], c.byref(width))
            rows.append(
                dict(
                    color=color,
                    p_cm3=density,
                    temperature_k=t,
                    fermi_level_ev=energy,
                    panel=panel,
                    style=style,
                    path_index=index,
                    marker_path_index=marker,
                    lorenz_1e8=val,
                    fig5_status="visible" if val is not None else "clipped_above_panel",
                    visual_halfwidth_1e8=width.value * 0.5 * span / (high - low),
                    fig6_path_index=findex,
                    fig6_lorenz_1e8=fval,
                    fig6_status="visible" if fval is not None else "clipped_above_panel",
                    fig5_minus_fig6_1e8=None if val is None or fval is None else val - fval,
                )
            )
with (OUT / "slices.csv").open("w") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
# Deterministic checks of the endpoint-panel orderings.
for t, order in [(300, ["blue", "black", "red"]), (850, ["black", "blue"])]:
    vals = {
        r["color"]: r["lorenz_1e8"]
        for r in rows
        if r["panel"] == "5c" and r["temperature_k"] == t and r["style"] == "solid"
    }
    assert all(vals[a] > vals[b] for a, b in zip(order, order[1:], strict=False))
record = dict(
    source=str(SOURCE),
    sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    pdf_page_index=7,
    printed_page="125206-8",
    pdfium_version=str(pdfium.PYPDFIUM_INFO),
    method="Linear intersection within native PDF polyline segments; affine tick-center calibration; no extrapolation. Fig5c only includes 300 and 850 K; 483 and 667 K taken from Fig5b.",  # noqa: E501
    assumptions="Marker energies fixed at all temperatures; literal published marker/legend colors retained. These slices are not a recalculation of a temperature-dependent chemical potential at fixed density.",  # noqa: E501
    clipping="Fig5c 850 K red marker is beyond the visible solid path endpoint at the upper L=2.5 boundary; report missing, not extrapolated. Fig6 solid curves terminate at upper L=2.2 boundary; 850 K solid values unavailable. Dotted Fig6 endpoint maps to 849.992857 K and is snapped to 850 K within the published-axis 0.1 K calibration envelope. No inferred values beyond clipped path endpoints.",  # noqa: E501
    uncertainty="Visual halfwidth is half the published stroke width converted to L, not statistical sigma. Fig5b has a 0..30 ordinate and thus coarser visual precision than Fig5c; native centerline intersections are reproducible but do not establish corresponding physical precision.",  # noqa: E501
    conclusion="For direct fixed-energy slices, Fig5c at 300 K orders blue > black > red, opposite to Fig6. At 667 K Fig5b orders red > black > blue, opposite to Fig6. At 483 K the fixed slices order red > blue > black, while Fig6 orders red > black > blue; the small differences in Fig5b are below the plotted stroke halfwidth. A red/blue reversal agrees qualitatively with separated low/high-temperature ordering, but is not proof of a label error: fixed-energy slices and fixed-density temperature paths need not be the same calculation.",  # noqa: E501
)
(OUT / "record.json").write_text(json.dumps(record, indent=2) + "\n")
for r in rows:
    print(r["temperature_k"], r["color"], r["style"], r["lorenz_1e8"], r["fig6_lorenz_1e8"])
