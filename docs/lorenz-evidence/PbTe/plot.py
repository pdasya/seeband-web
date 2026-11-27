"""Compare calibrated PDF paths with the fixed-density calculation. Run after compare.py."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

out = Path(__file__).resolve().parent
ref = pd.read_csv(out / "reference.csv")
model = pd.read_csv(out / "seeband.csv").query('scenario=="density"')
densities = [1.5, 2.0, 2.5]
colors = ["#34548b", "#d89032", "#71826a", "#8974ab", "#ce5453"]
components = ["L_weighted_L", "Sigma_weighted_L", "C_weighted_L", "hole_hole", "bipolar"]
labels = ["L holes", "Σ holes", "C electrons", "Hole–hole mixing", "Electron–hole (bipolar)"]
fig, axs = plt.subplots(2, 3, figsize=(12, 7.4), sharex=True, sharey="row")
fig.subplots_adjust(left=0.073, right=0.985, top=0.83, bottom=0.15, hspace=0.28, wspace=0.12)
fig.suptitle("p-type PbTe  ·  Lorenz number at fixed net hole density", fontsize=16, y=0.98)
metrics = []
for i, p in enumerate(densities):
    d = model[model.p20 == p]
    a, b = axs[:, i]
    a.set_title(f"p = {p:.1f} × 10²⁰ cm⁻³", fontsize=11)
    for style, column, ls in [("solid", "total", "-"), ("dotted", "intraband", ":")]:
        r = ref[(ref.p_cm3 == p * 1e20) & (ref["style"] == style)].sort_values("temperature_k")
        a.plot(r.temperature_k, r.lorenz_1e8_w_ohm_k2, color="#1f2530", ls=ls, lw=2.1)
        a.plot(d.T_K, d[column], color="#148179", ls=ls, lw=2.1)
        delta = np.interp(r.temperature_k, d.T_K, d[column]) - r.lorenz_1e8_w_ohm_k2
        metrics.append(
            dict(
                p20=p,
                reference=style,
                n=len(r),
                T_min=r.temperature_k.min(),
                T_max=r.temperature_k.max(),
                rmse=(delta @ delta / len(r)) ** 0.5,
                max_abs=abs(delta).max(),
            )
        )
    if p == 2.5:
        a.plot(850, 2.9, "*", color="#1f2530", ms=11)
    b.stackplot(d.T_K, *[d[c] for c in components], colors=colors, linewidth=0)
    b.plot(d.T_K, d.total, color="#303030", lw=1)
    for ax in [a, b]:
        ax.grid(axis="y", alpha=0.18)
        ax.spines[["right", "top"]].set_visible(False)
        ax.set_xlim(292, 862)
        ax.set_xticks([300, 450, 600, 750, 850])
        ax.tick_params(labelsize=9)
    b.set_xlabel("Temperature (K)")
axs[0, 0].set_ylim(1.4, 3.8)
axs[1, 0].set_ylim(0, 3.8)
axs[0, 0].set_ylabel("L (10⁻⁸ W Ω K⁻²)")
axs[1, 0].set_ylabel("Contributions to L\n(10⁻⁸ W Ω K⁻²)")
handles = [
    Line2D([], [], c="#1f2530", lw=2, label="Thesberg, Fig. 6"),
    Line2D([], [], c="#148179", lw=2, label="SeeBand moments"),
    Line2D([], [], c="#666", ls="-", label="Total"),
    Line2D([], [], c="#666", ls=":", label="Weighted bands"),
    Line2D([], [], c="#1f2530", marker="*", ls="none", label="Text estimate at 850 K"),
]
fig.legend(
    handles=handles,
    loc="upper center",
    bbox_to_anchor=(0.5, 0.937),
    ncol=5,
    frameon=False,
    fontsize=9,
)
fig.legend(
    handles=[Patch(color=c, label=l) for c, l in zip(colors, labels, strict=False)],  # noqa: E741
    loc="lower center",
    bbox_to_anchor=(0.5, 0.033),
    ncol=5,
    frameon=False,
    fontsize=9,
)
fig.text(
    0.5,
    0.014,
    "Top: extracted lines end at the printed frame. Bottom: model decomposition; one effective valley per quoted mass.",  # noqa: E501
    ha="center",
    fontsize=9,
    color="#414953",
)
fig.savefig(out / "PbTe-Fig6.png", dpi=175)
pd.DataFrame(metrics).to_csv(out / "metrics.csv", index=False)
