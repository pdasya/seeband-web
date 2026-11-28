# ruff: noqa: T201 -- print replay results for reviewers.
"""Reproduce manual, image-only S7 beta=1 digitization; no physical model.
Run with a Python containing pypdfium2 and Pillow, e.g. the scientific-pdf venv.
"""

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("pdf", type=Path)
parser.add_argument("--out", type=Path, default=Path(__file__).parent)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
assert (
    hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    == "1131f062bd5dca7915fe01ff72a0f2bba46ba0a836c860cb1ddcaf40535ef971"
), "Source PDF hash mismatch"
pdf = pdfium.PdfDocument(args.pdf)
page = pdf[48]
images = [obj for obj in page.get_objects() if obj.type == 3]
assert len(images) == 1
im = images[0].get_bitmap().to_pil().convert("RGB")
assert im.size == (1387, 399)
im.save(args.out / "s7_source_embedded.png")
page.render(scale=3).to_pil().save(args.out / "source_page49.png")
(args.out / "source_page49.txt").write_text(page.get_textpage().get_text_range())
# Native image coordinates, origin top left. Calibrated on visible tick centers.
# x=110 => gap=4; x=443 => gap=10; y=299 => ratio=1; y=61 => ratio=1.8.
x0, x1, y0, y1 = 110.0, 443.0, 299.0, 61.0
sx = (x1 - x0) / 6
sy = (y0 - y1) / 0.8
# Center readings are manual coordinates on the native lossless embedded raster.
# None records an entirely hidden marker; no physics supplies its central value.
centers = {
    "sigma": [291.0, 296.0, 298.0, 299.0, None, None, 299.0],
    "abs_S": [326.0, 310.0, 303.5, 301.0, 300.0, 299.5, 299.0],
    "kappa_el": [50.0, 184.0, 247.5, 278.0, 291.0, 296.5, 299.0],
}
rows = []
pixel_records = []
for quantity, yy in centers.items():
    for gap, yc in zip(range(4, 11), yy, strict=False):
        xc = x0 + (gap - 4) * sx
        status = "visible"
        note = "Manual native-raster marker center; full-glyph coordinate envelope."
        half = 6.0
        if (quantity == "sigma" and gap in (6, 7)) or (quantity != "sigma" and gap >= 8):
            status, half = "partial_overlap", 7.0
            note = "Marker partly overlaps another quantity; widened full-glyph envelope."
        if yc is None:
            # All colored glyph pixels in the local overlap cluster, plus 1 px.
            yl, yh = {8: (286.0, 305.0), 9: (292.0, 304.0)}[gap]
            status = "unavailable_overlap"
            note = "No independent blue center visible; bounds cover the complete colored overlap cluster plus 1px. No central ratio supplied."  # noqa: E501
        else:
            yl, yh = yc - half, yc + half
        ratio = "" if yc is None else 1 + (y0 - yc) / sy
        if gap == 10:
            ratio = 1.0
            status = "normalization_anchor_overlap"
            note = "Exact center=1 is source-defined normalization, not an independently resolved raster coordinate; envelope is digitization only."  # noqa: E501
        low, high = 1 + (y0 - yh) / sy, 1 + (y0 - yl) / sy
        rows.append(
            dict(
                quantity=quantity,
                beta=1,
                gap_kbt=gap,
                gap_kbt_low=round(gap - 6 / sx, 6),
                gap_kbt_high=round(gap + 6 / sx, 6),
                ratio="" if ratio == "" else round(ratio, 6),
                ratio_low=round(low, 6),
                ratio_high=round(high, 6),
                status=status,
                notes=note,
            )
        )
        pixel_records.append(
            dict(
                quantity=quantity,
                gap_kbt=gap,
                x_px=xc,
                y_px=yc,
                x_low_px=xc - 6,
                x_high_px=xc + 6,
                y_low_px=yl,
                y_high_px=yh,
            )
        )
assert len(rows) == 21
assert sum(r["ratio"] == "" for r in rows) == 2
assert all(r["ratio_low"] <= r["ratio_high"] for r in rows)
assert all(r["ratio"] == "" or r["ratio_low"] <= r["ratio"] <= r["ratio_high"] for r in rows)
with (args.out / "s7_beta1_digitized.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0])
    writer.writeheader()
    writer.writerows(rows)
# Overlay shows the complete native figure and uncertainty rectangles on beta=1.
overlay = im.resize((im.width * 3, im.height * 3), Image.Resampling.NEAREST)
draw = ImageDraw.Draw(overlay)
colors = {"sigma": "#c000c0", "abs_S": "#d05000", "kappa_el": "#008080"}
for p in pixel_records:
    color = colors[p["quantity"]]
    draw.rectangle(
        tuple(round(v * 3) for v in (p["x_low_px"], p["y_low_px"], p["x_high_px"], p["y_high_px"])),
        outline=color,
        width=2,
    )
    if p["y_px"] is not None:
        x, y = p["x_px"] * 3, p["y_px"] * 3
        draw.line((x - 5, y, x + 5, y), fill=color, width=2)
        draw.line((x, y - 5, x, y + 5), fill=color, width=2)
overlay.save(args.out / "s7_beta1_overlay.png")
metadata = dict(
    source_url="https://arxiv.org/pdf/2603.21649",
    source_pdf_path=args.pdf.name,
    source_sha256=hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
    pdf_page_one_based=49,
    printed_supplement_page=12,
    figure="Supplementary Fig. 7, left beta=1.0 panel",
    method="Manual native embedded raster coordinates; linear tick calibration; no interpolation, fit, model, or core calculation.",  # noqa: E501
    native_raster_size_px=list(im.size),
    axis_calibration=dict(x_gap4_px=x0, x_gap10_px=x1, y_ratio1_px=y0, y_ratio1_8_px=y1),
    coordinate_equations={"gap_kbt": "4 + (x-110)*6/333", "ratio": "1 + (299-y)*0.8/238"},
    legend={
        "sigma": "blue circle: sigma",
        "abs_S": "orange square: |S|",
        "kappa_el": "green upward triangle: kappa_el",
    },
    normalization="Each quantity at mu=0 relative to its corresponding value at Eg=10 kBT. abs_S is a magnitude ratio, not signed S.",  # noqa: E501
    coverage="All seven marker positions gap_kbt=4..10 in beta=1 panel. No data supplied outside plotted range. Straight connecting segments are not extra sampled data.",  # noqa: E501
    uncertainty="Deterministic coordinate envelopes, not statistical confidence intervals or paper error bars. Isolated markers use center +/-6 native px vertically (entire ~9-10px glyph plus calibration/read allowance); partial overlaps +/-7px; x always +/-6px. Hidden sigma at gaps8,9 uses the entire local colored glyph cluster plus1px with no central estimate. Calibration/read errors are shared, so intervals are not independent.",  # noqa: E501
    unavailable=[
        {
            "quantity": "sigma",
            "gap_kbt": g,
            "reason": "Blue glyph fully occluded by later-drawn colored glyphs.",
        }
        for g in (8, 9)
    ],
    pixel_records=pixel_records,
    versions={k: importlib.metadata.version(k) for k in ("pypdfium2", "Pillow")},
    python=platform.python_version(),
    checks=[
        "Legend, beta label, axis ticks, caption and normalization prose inspected on original page image.",  # noqa: E501
        "21 rows:3 quantities x7 gaps; exactly2 unavailable centers; all finite centers inside envelopes.",  # noqa: E501
    ],
)
(args.out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
print("Validated 21 digitized rows; 2 unavailable sigma centers; source and overlay saved.")
