# ruff: noqa: T201 -- print replay results for reviewers.
"""Image-only trace of published Hattori Supplement S4 d/e/f. No transport model."""

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

OUT = Path(__file__).resolve().parent
SRC = OUT / "source.pdf"
NATIVE = OUT / "s4-native.png"
assert NATIVE.exists(), "Extract native image from source.pdf as documented in README.md"
assert (
    hashlib.sha256(SRC.read_bytes()).hexdigest()
    == "1131f062bd5dca7915fe01ff72a0f2bba46ba0a836c860cb1ddcaf40535ef971"
), "Source PDF hash mismatch"
im = np.array(Image.open(NATIVE).convert("RGB")).astype(float)
# Source-image pixel centers; legends and axis tick marks visually checked.
panels = {
    "sigma": dict(
        panel="d",
        xlo=48,
        xhi=219,
        ytop=328,
        ybot=364,
        mu0=143.5,
        px_per_ev=123.0,
        zero_y=363.0,
        unit_per_px=1e6 / 19.625,
        unit="S/m",
        seeds=list(range(351, 330, -2)),
    ),
    "seebeck": dict(
        panel="e",
        xlo=280,
        xhi=450,
        ytop=210,
        ybot=362,
        mu0=374.5,
        px_per_ev=123.0,
        zero_y=361.5,
        unit_per_px=200 / 37.5,
        unit="uV/K",
        seeds=[214.5] * 5 + [215.5, 228, 246, 265, 284, 304],
    ),
    "kappa_el": dict(
        panel="f",
        xlo=507,
        xhi=677,
        ytop=210,
        ybot=359,
        mu0=602.5,
        px_per_ev=123.0,
        zero_y=358.0,
        unit_per_px=10 / 41.5,
        unit="W/(m K)",
        seeds=[308, 299, 290, 280, 270, 261, 251, 242, 232, 223, 213],
    ),
}
# Saturated interior line pixels at well separated left edge, not legend antialias.
palette = np.array([im[y, 48] for y in range(351, 330, -2)])
raw = []
calibrated = []
tracks = {}
for quantity, c in panels.items():
    xs = np.arange(c["xlo"], c["xhi"] + 1)
    ys = np.arange(c["ytop"], c["ybot"] + 1)
    pix = im[c["ytop"] : c["ybot"] + 1, c["xlo"] : c["xhi"] + 1]
    dark = 255 - pix
    strength = np.linalg.norm(dark, axis=2)
    for j, color in enumerate(palette):
        # Project color onto the white-to-ink ray to permit antialiasing.
        ray = 255 - color
        ray = ray / np.linalg.norm(ray)
        projection = dark @ ray
        orth = np.sqrt(np.maximum(0, strength**2 - projection**2))
        cost = orth / (strength + 8) * 12 + 2 * np.exp(-projection / 12)
        # Penalize ink darker than the native curve, important for neutral ΔE=0.
        cost += np.maximum(0, projection - np.linalg.norm(255 - color) * 1.5) / 30
        cost = gaussian_filter(cost, (0.3, 0.3))
        reverse = quantity == "seebeck"
        work = cost[:, ::-1] if reverse else cost
        seed = c["seeds"][j] - c["ytop"]
        n, m = work.shape
        dp = work[:, 0] + ((np.arange(n) - seed) / 0.7) ** 2
        back = np.zeros((m, n), int)
        # Image-space continuity only; no mathematical curve or physical model fit.
        steps = range(0, 4)
        for x in range(1, m):
            opts = []
            for step in steps:
                prev = np.arange(n) - step
                ok = (prev >= 0) & (prev < n)
                z = np.full(n, 1e9)
                z[ok] = dp[prev[ok]] + 0.17 * step**2
                # S and declining σ/κ are visibly monotone at raster scale.
                z += 0.4 * (step < 0)
                opts.append(z)
            opts = np.array(opts)
            best = opts.argmin(axis=0)
            back[x] = np.arange(n) - np.array(list(steps))[best]
            dp = work[:, x] + opts[best, np.arange(n)]
        path = np.zeros(m, int)
        path[-1] = dp.argmin()
        for x in range(m - 1, 0, -1):
            path[x - 1] = back[x, path[x]]
        if reverse:
            path = path[::-1]
        y = ys[path].astype(float)
        if quantity == "seebeck" and j == 5:
            # Neutral ink identified visually at these columns; it is lost in merged ink to the left.  # noqa: E501
            anchors = np.array(
                [
                    [320, 352],
                    [340, 347.4],
                    [360, 337.2],
                    [380, 316.4],
                    [400, 286.4],
                    [420, 256],
                    [440, 227],
                    [450, 215],
                ]
            )
            y = np.interp(xs, anchors[:, 0], anchors[:, 1])
            hidden = xs < 320
            other = np.array([tracks[quantity, k][1] for k in range(5)])
            # Representative merged-ink center; its full ambiguity is retained below.
            y[hidden] = (other[:, hidden].min(0) + 357) / 2
        tracks[quantity, j] = (xs, y)
        for x, v in zip(xs, y, strict=False):
            raw.append(
                dict(
                    quantity=quantity,
                    delta_e_ev=round((j - 5) / 10, 1),
                    x_px=int(x),
                    y_px=float(v),
                    r=int(im[int(v), x, 0]),
                    g=int(im[int(v), x, 1]),
                    b=int(im[int(v), x, 2]),
                )
            )
# A shared grid is interpolation of raster traces, never extrapolation.
grid = np.round(np.arange(-0.75, 0.6001, 0.025), 6)
for quantity, c in panels.items():
    for j in range(11):
        xs, y = tracks[quantity, j]
        mu = (xs - c["mu0"]) / c["px_per_ev"]
        all_y = np.array([tracks[quantity, k][1] for k in range(11)])
        for m in grid:
            if m < mu[0] or m > mu[-1]:
                continue
            center = float(np.interp(m, mu, y))
            idx = int(np.argmin(abs(mu - m)))
            # Any unresolved neighboring center within 1.2 pixels joins the same envelope.
            near = abs(all_y[:, idx] - center) <= 1.2
            near[j] = True
            for _ in range(11):
                near |= np.min(abs(all_y[:, idx, None] - all_y[near, idx][None, :]), axis=1) <= 1.2
            lowpix = min(center, float(all_y[near, idx].min())) - 1.5
            hipix = max(center, float(all_y[near, idx].max())) + 1.5
            # Horizontal axis/tick placement ±0.5 pixel enters through observed local slope.
            slope = abs(float(np.gradient(y)[idx]))
            lowpix -= 0.5 * slope
            hipix += 0.5 * slope
            hidden_gray = quantity == "seebeck" and j == 5 and xs[idx] < 320
            if hidden_gray:
                lowpix = min(lowpix, float(all_y[:, idx].min()) - 1.5)
                hipix = max(hipix, float(all_y[:, idx].max()) + 1.5)
            floor = center >= c["zero_y"] - 2.5
            status = (
                "near_floor_unresolved"
                if floor
                else ("overlap_unresolved" if near.sum() > 1 or hidden_gray else "resolved")
            )
            value = max(0, (c["zero_y"] - center) * c["unit_per_px"])
            lower = max(0, (c["zero_y"] - hipix) * c["unit_per_px"])
            upper = max(0, (c["zero_y"] - lowpix) * c["unit_per_px"])
            calibrated.append(
                dict(
                    panel=c["panel"],
                    quantity=quantity,
                    delta_e_ev=round((j - 5) / 10, 1),
                    mu_ev=m,
                    value=value,
                    lower=lower,
                    upper=upper,
                    unit=c["unit"],
                    status=status,
                    source_y_px=center,
                    envelope_lo_y_px=lowpix,
                    envelope_hi_y_px=hipix,
                )
            )
for name, rows in [("raw_trace_pixels.csv", raw), ("digitized_curves.csv", calibrated)]:
    with (OUT / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
# Native-pixel overlay: black center markers avoid reproducing misleading smooth precision.
over = Image.open(NATIVE).convert("RGB").resize((2774, 1558))
draw = ImageDraw.Draw(over)
for (q, j), (xs, y) in tracks.items():  # noqa: B007
    for x, v in zip(xs[::8], y[::8], strict=False):
        draw.ellipse((2 * x - 1, 2 * v - 1, 2 * x + 1, 2 * v + 1), fill=(0, 0, 0))
over.crop((0, 390, 1390, 790)).save(OUT / "trace-overlay.png")
metadata = dict(
    source_pdf=SRC.name,
    source_sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(),
    pdf_page_one_based=46,
    printed_page=9,
    figure="Supplementary Fig. 4",
    gamma=-0.5,
    native_image_size=[1387, 779],
    native_sha256=hashlib.sha256(NATIVE.read_bytes()).hexdigest(),
    panels=panels,
    palette_rgb=palette.tolist(),
    grid_mu_ev=grid.tolist(),
    method="White-to-ink RGB ray separation and bounded image-space dynamic-programming continuity; linear pixel-to-axis calibration; linear resampling of extracted coordinates only.",  # noqa: E501
    envelope="Deterministic image-reading envelope, not statistical confidence interval: ±1.5 vertical pixels, ±0.5 horizontal pixel times local observed slope; envelope union for extracted neighboring traces within 1.2 px. Includes native line thickness, vertical calibration and quantization. Overlap centers are representatives, not independently resolved values.",  # noqa: E501
    manual_gray_seebeck_anchors_native_px=[
        [320, 352],
        [340, 347.4],
        [360, 337.2],
        [380, 316.4],
        [400, 286.4],
        [420, 256],
        [440, 227],
        [450, 215],
    ],
    no_extrapolation=True,
    notes=[
        "All 11 published DeltaE values included.",
        "No model or physical curve fit used.",
        "Native raster resolution limits separability, especially conductivity near baseline, S blue curves at positive mu, and red S curves at negative mu.",  # noqa: E501
        "Shared gray DeltaE=0 trace can be obscured by other ink.",
        "Values are positive as plotted; sigma original axis (ohm m)^-1 with 1e6 multiplier; S uV/K; kappa W/m/K.",  # noqa: E501
    ],
)
(OUT / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
assert len(calibrated) == 3 * 11 * len(grid)
assert all(r["lower"] <= r["value"] <= r["upper"] for r in calibrated)
assert all(
    any(
        r["mu_ev"] == 0 and r["quantity"] == q and r["delta_e_ev"] == round((j - 5) / 10, 1)
        for r in calibrated
    )
    for q in panels
    for j in range(11)
)
print(
    f"{len(raw)} raw pixels; {len(calibrated)} calibrated rows; 33 traces; mu=0 present for all. Envelope checks passed."  # noqa: E501
)
# Portable visual comparison in physical plot units, with explicitly image-derived envelopes.
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

fig, axes = plt.subplots(1, 3, figsize=(15, 4.4), constrained_layout=True)
for ax, (q, c) in zip(axes, panels.items(), strict=False):
    for j in range(11):
        r = [
            r
            for r in calibrated
            if r["quantity"] == q and r["delta_e_ev"] == round((j - 5) / 10, 1)
        ]
        x = np.array([v["mu_ev"] for v in r])
        v = np.array([v["value"] for v in r])
        lo = np.array([v["lower"] for v in r])
        hi = np.array([v["upper"] for v in r])
        col = palette[j] / 255
        ax.plot(x, v, color=col, lw=1, label=f"{(j - 5) / 10:+.1f}")
        ax.fill_between(x, lo, hi, color=col, alpha=0.10)
    ax.set(
        xlabel="Chemical potential μ (eV)",
        ylabel=f"{q} ({c['unit']})",
        title=f"S4{c['panel']}: γ = −0.5",
    )
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.15)
axes[-1].legend(title="ΔE (eV)", fontsize=7, ncol=2)
fig.savefig(OUT / "digitized-envelopes.png", dpi=180)
plt.close(fig)
from collections import Counter  # noqa: E402

counts = Counter(r["status"] for r in calibrated)
(OUT / "validation.json").write_text(
    json.dumps(
        dict(
            raw_rows=len(raw),
            common_grid_rows=len(calibrated),
            trace_count=33,
            common_grid_points=55,
            status_counts=dict(counts),
            all_mu_zero_present=True,
            all_bounds_contain_centers=True,
            native_mu_domains={
                q: [(c["xlo"] - c["mu0"]) / c["px_per_ev"], (c["xhi"] - c["mu0"]) / c["px_per_ev"]]
                for q, c in panels.items()
            },
            color_anchor_reproduction_checks={
                "sigma_x48_max_seed_error_px": max(
                    abs(tracks["sigma", j][1][0] - panels["sigma"]["seeds"][j]) for j in range(11)
                ),
                "kappa_x507_max_seed_error_px": max(
                    abs(tracks["kappa_el", j][1][0] - panels["kappa_el"]["seeds"][j])
                    for j in range(11)
                ),
            },
        ),
        indent=2,
    )
    + "\n"
)
