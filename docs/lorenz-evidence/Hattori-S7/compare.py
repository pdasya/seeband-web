# ruff: noqa: T201 -- print replay results for reviewers.
"""Compare the nominal x values of the published markers. No fitted parameters."""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

out = Path(__file__).resolve().parent
raw = pd.read_csv(sys.argv[1])
model = pd.read_csv(out / "model.csv")
raw.quantity = raw.quantity.replace({"|S|": "S", "abs_S": "S", "kappa_el": "kappa"})
assert set(raw.quantity) == {"sigma", "S", "kappa"}
rows = []
for gap, group in raw.groupby("gap_kbt"):
    points = group.set_index("quantity")
    entries = {}
    for name in ("sigma", "S", "kappa"):
        p = points.loc[name]
        entries[name] = (p.ratio, p.ratio_low, p.ratio_high, p.status)
    sg, sl, su, _ = entries["sigma"]
    kg, kl, ku, _ = entries["kappa"]
    if gap == 10:
        entries["L"] = (1.0, 1.0, 1.0, "normalization")
    else:
        entries["L"] = (
            kg / sg,
            kl / su,
            ku / sl,
            "source quotient" if np.isfinite(sg) and np.isfinite(kg) else "bounded quotient",
        )
    for name, (value, lower, upper, status) in entries.items():
        calc = np.interp(gap, model.gap_kbt, model[name + "_ratio"])
        rows.append(
            dict(
                gap_kbt=gap,
                quantity=name,
                paper=value,
                lower=lower,
                upper=upper,
                model=calc,
                delta=calc - value,
                relative_delta_pct=100 * (calc / value - 1),
                inside=(lower <= calc <= upper),
                independent_comparison=gap != 10,
                source_status=status,
            )
        )
df = pd.DataFrame(rows)
df.to_csv(out / "comparison.csv", index=False)
fig, axes = plt.subplots(2, 2, figsize=(10, 7), layout="constrained")
for ax, name, label in zip(
    axes.flat,
    ["sigma", "S", "kappa", "L"],
    ["σ / σ₁₀", "|S| / |S₁₀|", "κₑₗ / κₑₗ,₁₀", "L / L₁₀"],
    strict=False,  # noqa: E501
):
    sub = df[df.quantity == name]
    ax.plot(model.gap_kbt, model[name + "_ratio"], color="#176f83", lw=2, label="SeeBand")
    for tag, data in sub.groupby("independent_comparison"):
        if not tag:
            ax.scatter(
                data.gap_kbt,
                np.ones(len(data)),
                s=43,
                marker="s",
                facecolors="white",
                edgecolors="#4c4c4c",
                zorder=4,
                label="Normalization",
            )
            continue
        known = data[data.paper.notna()]
        ax.errorbar(
            known.gap_kbt,
            known.paper,
            yerr=[known.paper - known.lower, known.upper - known.paper],
            fmt="o",
            ms=4,
            color="#202432",
            capsize=3,
            label="Digitized value and reading bounds",
        )
        unknown = data[data.paper.isna()]
        if len(unknown):
            ax.vlines(
                unknown.gap_kbt,
                unknown.lower,
                unknown.upper,
                color="#c05b16",
                linewidth=3,
                label="Occlusion bounds only",
            )
    ax.axhline(1, color="0.7", lw=0.6)
    ax.set(xlabel="Eɡ / kBT", ylabel=label, xticks=range(4, 11))
    ax.grid(alpha=0.2)
axes[0, 0].legend(fontsize=7)
fig.suptitle("Hattori et al. · Supplementary Fig. 7 · β = 1")
fig.savefig(out / "comparison.png", dpi=175)
print(df.to_string(index=False))
