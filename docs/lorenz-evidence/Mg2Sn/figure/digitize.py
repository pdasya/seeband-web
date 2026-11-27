# ruff: noqa: T201 -- print replay results for reviewers.
"""Digitize Naithani Fig.3 raster; run with the installed Docling Python.
Native pixel coordinate convention: x rightwards, y downwards, origin upper left.
No fitting, smoothing, or extrapolation. Omit obscured/unresolvable pixels.
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import ImageDraw
from scipy.ndimage import find_objects, label

OUT = Path(__file__).resolve().parent
SOURCE = Path(sys.argv[1])
doc = pdfium.PdfDocument(SOURCE)
page = doc[8]
images = list(page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]))
assert len(images) == 1
im = images[0].get_bitmap().to_pil().convert("RGB")
im.save(OUT / "source-figure3.png")
a = np.asarray(im).astype(int)
r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
masks = dict(
    red=(r > 150) & (g < 110) & (b < 110),
    blue=(b > 140) & (r < 110) & (g < 120),
    magenta=(r > 150) & (b > 150) & (g < 125),
    green=(g > 50) & (g < 180) & (r < 90) & (b < 100),
    olive=(r > 65) & (g > 65) & (r < 180) & (g < 180) & (b < 90) & (abs(r - g) < 50),
    orange=(r > 180) & (g > 65) & (g < 190) & (b < 90),
    lime=(g > 180) & (r < 100) & (b < 120),
)
# Tick center calibration visually checked on the original embedded figure.
# panel: x0,T0,x1,T1,y0,value0,y1,value1 (conductivity panel b split).
axes = dict(
    a=[126, 300, 639, 750, 11, 0, 447, -200],
    c=[106, 300, 652, 750, 548, 350, 912, 0],
    b_upper=[778, 250, 1325, 750, 20, 5000, 328, 2000],
    b_lower=[778, 250, 1325, 750, 345, 1000, 449, 0],
    d=[785, 300, 1329, 750, 561, 4000, 999, 0],
)
# Approximate guide anchors choose the curve when symbols of the same color
# coexist in a column. Output ordinates are actual colored pixel run centers,
# never the guide values. Gaps remain gaps. Anchors are reproducible choices.
samples = {
    "n_sc_sb": ("n", "Sc0.05Mg2.01Sn0.97Sb0.03", "red", 4.57e20),
    "n_sb": ("n", "Mg2.06Sn0.97Sb0.03", "blue", 3.97e20),
    "n_sc05": ("n", "Sc0.05Mg1.95Sn", "magenta", 2e18),
    "n_sc01": ("n", "Sc0.01Mg1.99Sn", "green", 4e17),
    "p_li03": ("p", "Li0.03Mg1.97Sn", "olive", 2.69e20),
    "p_li02": ("p", "Li0.02Mg1.98Sn", "blue", 2.45e20),
    "p_li01": ("p", "Li0.01Mg1.99Sn", "magenta", 1.51e20),
    "p_li005": ("p", "Li0.005Mg1.995Sn", "green", 7.2e19),
    "p_undoped": ("p", "Mg2Sn", "orange", 4.4e18),
}
curves = [
    ("a", "n_sc_sb", [(300, -70), (400, -90), (500, -111), (600, -128), (700, -138), (750, -140)]),
    ("a", "n_sb", [(300, -77), (400, -98), (500, -117), (600, -134), (700, -145), (750, -147)]),
    (
        "a",
        "n_sc05",
        [
            (350, -200),
            (400, -112),
            (450, -69),
            (500, -44),
            (550, -35),
            (600, -31),
            (650, -30),
            (750, -29),
        ],
    ),
    (
        "a",
        "n_sc01",
        [(300, -144), (350, -60), (400, -33), (450, -26), (500, -24), (600, -25), (750, -27)],
    ),
    (
        "c",
        "p_li03",
        [(300, 50), (400, 70), (500, 88), (600, 99), (650, 104), (700, 108), (750, 105)],
    ),
    (
        "c",
        "p_li02",
        [(300, 55), (400, 76), (500, 94), (600, 106), (650, 110), (700, 111), (750, 105)],
    ),
    (
        "c",
        "p_li01",
        [
            (300, 80),
            (400, 102),
            (500, 120),
            (550, 125),
            (600, 128),
            (650, 127),
            (700, 120),
            (750, 105),
        ],
    ),
    (
        "c",
        "p_li005",
        [
            (300, 120),
            (400, 150),
            (500, 158),
            (550, 153),
            (600, 136),
            (650, 112),
            (700, 88),
            (750, 68),
        ],
    ),
    (
        "c",
        "p_undoped",
        [
            (300, 315),
            (350, 260),
            (400, 155),
            (450, 75),
            (500, 30),
            (550, 10),
            (600, -5),
            (650, -12),
            (750, -20),
        ],
    ),
    (
        "b_upper",
        "n_sc_sb",
        [
            (350, 4500),
            (400, 3900),
            (450, 3400),
            (500, 3040),
            (550, 2750),
            (600, 2490),
            (650, 2300),
            (730, 2000),
        ],
    ),
    (
        "b_upper",
        "n_sb",
        [
            (300, 5100),
            (350, 4300),
            (400, 3600),
            (450, 3200),
            (500, 2850),
            (550, 2550),
            (600, 2280),
            (660, 2000),
        ],
    ),
    # n_sc05 b_lower is fully ambiguous with its magenta square edges and
    # the overpainted green curve: no independent published solid stroke.
    ("b_lower", "n_sc01", [(300, 0), (400, 80), (500, 190), (600, 340), (700, 490), (750, 600)]),
    ("d", "p_li03", [(300, 3200), (400, 2400), (500, 1900), (600, 1570), (700, 1350), (750, 1260)]),
    ("d", "p_li02", [(300, 3100), (400, 2300), (500, 1800), (600, 1450), (700, 1250), (750, 1170)]),
    ("d", "p_li01", [(300, 2200), (400, 1630), (500, 1250), (600, 1010), (700, 890), (750, 870)]),
    ("d", "p_li005", [(300, 1250), (400, 850), (500, 670), (600, 600), (700, 630), (750, 670)]),
    ("d", "p_undoped", [(300, 110), (400, 130), (500, 230), (600, 370), (700, 510), (750, 600)]),
]


def field_y(ax):
    return (548, 990) if ax == "c" else tuple(sorted((axes[ax][4], axes[ax][6])))


def xy(ax, t, v):
    x0, t0, x1, t1, y0, v0, y1, v1 = axes[ax]
    return x0 + (t - t0) * (x1 - x0) / (t1 - t0), y0 + (v - v0) * (y1 - y0) / (v1 - v0)


def values(ax, x, y):
    x0, t0, x1, t1, y0, v0, y1, v1 = axes[ax]
    return t0 + (x - x0) * (t1 - t0) / (x1 - x0), v0 + (y - y0) * (v1 - v0) / (y1 - y0)


def runs(ys):
    return np.split(ys, np.where(np.diff(ys) > 1)[0] + 1) if len(ys) else []


def base(ax, sid, x, y, kind):
    carrier, composition, color, density = samples[sid]
    t, v = values(ax, x, y)
    unit = "uV/K" if ax in ("a", "c") else "S/cm"
    dx = abs(axes[ax][3] - axes[ax][1]) / abs(axes[ax][2] - axes[ax][0])
    dy = abs(axes[ax][7] - axes[ax][5]) / abs(axes[ax][6] - axes[ax][4])
    return dict(
        panel=ax[0],
        axis_segment=ax,
        sample_id=sid,
        composition=composition,
        carrier_type=carrier,
        color=color,
        extrinsic_density_cm3=density,
        kind=kind,
        temperature_k=t,
        value=v,
        unit=unit,
        value_si=v * (1e-6 if unit == "uV/K" else 100),
        si_unit="V/K" if unit == "uV/K" else "S/m",
        digitization_temperature_envelope_k=2 * dx,
        digitization_value_envelope=2 * dy,
        pixel_x=x,
        pixel_y=y,
    )


rows = []
for ax, sid, anchors in curves:
    color = samples[sid][2]
    mask = masks[color].copy()
    # Remove isolated small components (symbols) before looking for curves.
    lab, _ = label(mask)
    for k, sl in enumerate(find_objects(lab), 1):
        if (
            sl is not None
            and 7 <= sl[0].stop - sl[0].start < 24
            and 7 <= sl[1].stop - sl[1].start < 24
        ):
            mask[sl] &= lab[sl] != k
    anchor_t, anchor_v = np.array(anchors).T
    start, end = xy(ax, anchor_t[0], anchor_v[0])[0], xy(ax, anchor_t[-1], anchor_v[-1])[0]
    for x in range(max(0, int(np.ceil(start))), min(im.width, int(end) + 1)):
        t, _ = values(ax, x, 0)
        guide_y = xy(ax, t, np.interp(t, anchor_t, anchor_v))[1]
        slope = abs(xy(ax, t + 1, np.interp(t + 1, anchor_t, anchor_v))[1] - guide_y) / abs(
            xy(ax, t + 1, 0)[0] - x
        )
        max_width = 6 + int(np.ceil(slope))
        candidates = [
            z
            for z in runs(np.flatnonzero(mask[:, x]))
            if len(z) <= max_width and abs(np.mean(z) - guide_y) < 12
        ]
        if not candidates:
            continue
        z = min(candidates, key=lambda z: abs(np.mean(z) - guide_y))
        y = float(np.mean(z))
        # Omit neighborhoods where a touching symbol broadens the curve.
        contaminated = False
        for xx in range(max(0, x - 5), min(im.width, x + 6)):
            tt, _ = values(ax, xx, 0)
            shift = xy(ax, tt, np.interp(tt, anchor_t, anchor_v))[1] - guide_y
            if any(
                len(zz) > max_width and abs(float(np.mean(zz)) - y - shift) < 10
                for zz in runs(np.flatnonzero(mask[:, xx]))
            ):
                contaminated = True
                break
        if contaminated:
            continue
        # Crop to the actual plotting field, excluding labels and off-scale values.
        if field_y(ax)[0] + 1 <= y <= field_y(ax)[1] - 1:
            rows.append(base(ax, sid, x, y, "published_2PB_curve"))
# Isolated connected symbols only. Components connected to lines or touching
# another symbol are omitted rather than assigned an invented center.
markers = []
for ax, sid, _ in curves:
    mask = masks[samples[sid][2]].copy()
    x0, _, x1, _, y0, _, y1, _ = axes[ax]
    roi = np.zeros_like(mask)
    roi[field_y(ax)[0] + 3 : field_y(ax)[1] - 2, min(x0, x1) + 3 : max(x0, x1) - 2] = True
    # Legend rectangles (including their isolated symbols).
    legends = {
        "a": [(383, 140, 634, 261), (238, 397, 608, 436)],
        "c": [(400, 549, 653, 744), (160, 941, 431, 982)],
        "b_upper": [(1000, 29, 1306, 169)],
        "b_lower": [(810, 352, 1186, 393)],
        "d": [(1008, 564, 1313, 781)],
    }
    for l, t, rgt, bot in legends.get(ax, []):  # noqa: E741
        roi[t:bot, l:rgt] = False
    labels, count = label(mask & roi)
    for k, sl in enumerate(find_objects(labels), 1):
        if sl is None:
            continue
        sy, sx = sl
        w, h = sx.stop - sx.start, sy.stop - sy.start
        pixels = np.argwhere(labels[sl] == k)
        if 7 <= w <= 18 and 7 <= h <= 18 and len(pixels) >= 35:
            # Filled-marker area centroid preserves the plotting center of
            # regular triangles as well as circles and squares.
            y = float(sy.start + pixels[:, 0].mean())
            x = float(sx.start + pixels[:, 1].mean())
            markers.append(base(ax, sid, x, y, "experimental_symbol_isolated"))

# Overlapping lower-panel squares whose outer edges remain identifiable.
# Green full squares obtained from >=7px vertical runs; boxes checked on a
# 4x crop. Four magenta boxes have BOTH top and bottom strips visible.
# No center is inferred from a single surviving edge.
identifiable_boxes = {
    "n_sc01": [
        (1183, 1195, 403, 415),
        (1165, 1175, 406, 418),
        (1144, 1155, 410, 421),
        (1123, 1134, 413, 424),
        (1102, 1114, 416, 427),
        (1081, 1093, 419, 430),
        (1060, 1071, 422, 433),
        (1039, 1051, 424, 436),
        (1018, 1030, 427, 438),
        (998, 1009, 429, 441),
        (976, 987, 432, 443),
        (955, 965, 434, 445),
        (932, 944, 436, 447),
        (911, 922, 438, 448),
        (889, 900, 439, 450),
        (866, 877, 440, 451),
        (827, 838, 442, 453),
    ],
    "n_sc05": [
        (878, 887, 439, 450),
        (900, 909, 438, 448),
        (921, 931, 436, 447),
        (944, 953, 435, 445),
    ],
}
for sid, boxes in identifiable_boxes.items():
    for l, r, t, b in boxes:  # noqa: E741
        markers.append(
            base(
                "b_lower", sid, (l + r) / 2, (t + b) / 2, "experimental_square_identifiable_overlap"
            )
        )


def write(name, data):
    assert data
    with (OUT / name).open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)


write("published-2pb-curves.csv", rows)
write("experimental-isolated-symbols.csv", markers)
# Bright lime is unique to the dashed SPB curves, so no guide is necessary.
spb = []
for ax, sid in [
    ("a", "n_sc_sb"),
    ("b_upper", "n_sc_sb"),
    ("b_lower", "n_sc_sb"),
    ("c", "p_li03"),
    ("d", "p_li03"),
]:
    x0, _, x1, _, y0, _, y1, _ = axes[ax]
    mask = masks["lime"].copy()
    for l, t, rgt, bot in {  # noqa: E741
        "a": [(383, 140, 634, 261), (238, 397, 608, 436)],
        "c": [(400, 549, 653, 744), (160, 941, 431, 982)],
        "b_upper": [(1000, 29, 1306, 169)],
        "b_lower": [(810, 352, 1186, 393)],
        "d": [(1008, 564, 1313, 781)],
    }[ax]:
        mask[t:bot, l:rgt] = False
    for x in range(x0 + 2, x1 - 1):
        for z in runs(np.flatnonzero(mask[min(y0, y1) + 2 : max(y0, y1) - 1, x])):
            if len(z) <= 8:
                y = float(np.mean(z)) + min(y0, y1) + 2
                row = base(ax, sid, x, y, "published_SPB_curve")
                row["color"] = "lime"
                spb.append(row)
write("published-spb-curves.csv", spb)
# Audit overlay: black dots every fifth extracted curve pixel; cyan crosses
# at independently readable experimental centers. Review against source.
over = im.copy()
draw = ImageDraw.Draw(over)
for row in rows[::5]:
    x, y = row["pixel_x"], row["pixel_y"]
    draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill="black")
for row in markers:
    x, y = row["pixel_x"], row["pixel_y"]
    draw.line((x - 3, y, x + 3, y), fill="cyan", width=1)
    draw.line((x, y - 3, x, y + 3), fill="cyan", width=1)
over.save(OUT / "digitization-overlay.png")
record = dict(
    source_pdf=str(SOURCE),
    source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    source_url="https://elib.dlr.de/193456/",
    doi="10.1088/2515-7655/ac7fb8",
    pdf_page_one_based=9,
    printed_page=8,
    image_size_px=im.size,
    axes=axes,
    samples=samples,
    curve_guide_anchors=curves,
    identifiable_square_boxes=identifiable_boxes,
    pdfium_version=str(pdfium.PYPDFIUM_INFO),
    curve_pixel_rows=len(rows),
    spb_pixel_rows=len(spb),
    experimental_symbols=len(markers),
    isolated_experimental_symbols=sum(r["kind"] == "experimental_symbol_isolated" for r in markers),
    identifiable_overlap_symbols=sum(
        r["kind"] == "experimental_square_identifiable_overlap" for r in markers
    ),
    orange_seebeck_zero_crossing=dict(
        native_pixel_x_bracket=[449, 450],
        temperature_k_approx=583,
        figure_reading_envelope_k=8,
        note="Original thin orange stroke centers straddle S=0 between these columns; vertical ±2px envelope dominates near the shallow crossing.",  # noqa: E501
    ),
    method="Embedded raster extracted by PDFium. RGB masks; remove isolated components with both dimensions 7–23px (symbols); colored runs no thicker than 6px plus guide-slope allowance; nearest manual guide within 12 px; omit ±5px neighborhoods containing a run thicker than the slope-adjusted threshold within 10px of the guide-shifted curve. No interpolation of output. Isolated connected symbols plus explicitly checked overlapping square boxes.",  # noqa: E501
    uncertainty="Conservative ±2 native pixels for each reported coordinate: combines pixel location, anti-aliasing and tick calibration. This is a digitization envelope, not measurement uncertainty or statistical sigma. Local overlaps can create larger error; inspect overlay. Original experimental error bars are not supplied.",  # noqa: E501
    omissions="The b_lower/n_sc05 published curve is unavailable: magenta marks are square edges and green overpaints the solid curve. SPB dashed bright-green runs are in a separate CSV. Experimental symbols touching curves or one another are omitted unless complete square outer extents can be identified; those explicitly annotated boxes are separate kinds. Masked legend regions can obscure curves; no reconstruction is attempted. At same-color crossings or marker overlaps extracted curve pixels can be unreliable; validation overlay retained.",  # noqa: E501
    verification="Axes, labels, colors, sample identities and broken n-type conductivity axis visually checked on original PDF render and native image. S/cm converted to S/m by ×100 only in value_si. Negative n-type Seebeck signs preserved.",  # noqa: E501
)
(OUT / "digitize-record.json").write_text(json.dumps(record, indent=2) + "\n")
assert {r["sample_id"] for r in rows} == set(samples)
assert len(rows) > 3000 and len(markers) > 50
assert len({(r["panel"], r["sample_id"]) for r in rows}) == 17
assert not any(r["axis_segment"] == "b_lower" and r["sample_id"] == "n_sc05" for r in rows)
assert any(r["panel"] == "c" and r["sample_id"] == "p_undoped" and r["value"] < 0 for r in rows)
print(
    json.dumps(
        dict(
            curve_pixel_rows=len(rows),
            spb_pixel_rows=len(spb),
            experimental_symbols=len(markers),
            output=str(OUT),
        ),
        indent=2,
    )
)
