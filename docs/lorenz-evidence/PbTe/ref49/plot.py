from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

out = Path(__file__).resolve().parent
d = pd.read_csv(out / "bands.csv")
pub = pd.read_csv(out / "published-and-inferred.csv")
fig, ax = plt.subplots(2, 2, figsize=(10.5, 7.2), sharex=True, layout="constrained")
for a, key, label in zip(
    ax.ravel(),
    ["mu_eV", "L_sigma_pct", "Sigma_sigma_pct", "C_sigma_pct"],
    [
        "Chemical potential relative to C (eV)",
        "L-valley holes (% of σ)",
        "Σ-valley holes (% of σ)",
        "C-valley electrons (% of σ)",
    ],
    strict=False,
):
    for p, color in zip([1.5, 2, 2.5], ["#ba4438", "#36434c", "#1462a2"], strict=False):
        for case, ls in [("Pei_PB", "-"), ("previous", "--")]:
            ds = d[(d.p20 == p) & (d.case == case)]
            a.plot(ds["T"], ds[key], color=color, ls=ls, lw=2 if ls == "-" else 1.35)
        if key in ("mu_eV", "Sigma_sigma_pct"):
            obs = pub[(pub.p20 == p) & (pub["T"] % 50 == 0)]
            source_key = "mu_from_Sigma_eV" if key == "mu_eV" else "Sigma_sigma_pct"
            a.scatter(
                obs["T"], obs[source_key], facecolors="white", edgecolors=color, s=18, zorder=5
            )
    a.axvline(700, color="#999999", lw=0.8, ls=":")
    a.grid(alpha=0.15)
    a.set_title(label, fontsize=12)
    a.set_xlim(300, 850)
    a.spines[["right", "top"]].set_visible(False)
for a in ax[-1]:
    a.set_xlabel("Temperature (K)")
ax[0, 0].set_title("Chemical potential relative to C (eV) · circles inferred from [49]")
ax[1, 0].set_title("Σ-valley holes (% of σ) · circles from Fig. S3(b)")
ax[1, 1].set_yscale("log")
fig.suptitle("PbTe · Fixed net doping, three parabolic bands\n", fontsize=17)
fig.legend(
    handles=[
        Line2D([], [], c=c, label=f"{p} × 10²⁰ cm⁻³")
        for p, c in zip(("1.5", "2.0", "2.5"), ("#ba4438", "#36434c", "#1462a2"), strict=False)
    ]
    + [
        Line2D([], [], c="k", label="[49] inputs, intravalley"),
        Line2D([], [], c="k", ls="--", label="Previous calculation"),
    ],
    loc="upper center",
    bbox_to_anchor=(0.5, 0.954),
    ncol=5,
    fontsize=9,
    frameon=False,
)
fig.savefig(out / "mu-and-conductivity.png", dpi=160)
