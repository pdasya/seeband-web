from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

out = Path(__file__).resolve().parent
inv = pd.read_csv(out / "inverse.csv")
fig, ax = plt.subplots(1, 2, figsize=(9.6, 4), layout="constrained")
for color, group in inv.groupby("p20"):
    pigment = {1.5: "#bc423c", 2.0: "#383838", 2.5: "#276fb0"}[color]
    for a, t in zip(ax, (300, 850), strict=False):
        row = group[group["T"] == t].iloc[0]
        a.plot(row.fig5_inferred_mu_eV, color, "o", color=pigment, ms=8)
        if t == 850:
            marker = {1.5: -0.22010948, 2.0: -0.24607351, 2.5: -0.26597296}[color]
            a.plot(marker, color, "|", color=pigment, ms=15, mew=2.5)
for a, t in zip(ax, (300, 850), strict=False):
    a.set(
        yticks=[1.5, 2, 2.5],
        ylim=(1.3, 2.7),
        xlabel="Chemical potential relative to C (eV)",
        title=f"{t} K",
    )
    a.grid(alpha=0.2)
ax[0].set_ylabel("Hole density label on Fig. 6 (10²⁰ cm⁻³)")
ax[1].plot([], [], "o", color="0.25", label="Energy inferred from Figs. 5 and 6")
ax[1].plot([], [], "|", ms=13, mew=2, color="0.25", label="Marker in Fig. 5(c) for same label")
ax[1].legend(loc="center", bbox_to_anchor=(0.5, -0.29), frameon=False, fontsize=8)
fig.suptitle("PbTe  ·  source-only reconstruction from published curves")
fig.savefig(out / "source-order.png", dpi=180)
