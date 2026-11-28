# ruff: noqa: T201 -- print replay results for reviewers.
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

out = Path(__file__).resolve().parent
samples = pd.read_csv(out / "samples.csv")
model = pd.read_csv(out / "predictions.csv")
dsrc = []
for path, kind in [("published-2pb-curves", "2PB"), ("experimental-isolated-symbols", "data")]:
    d = pd.read_csv(out / "figure" / f"{path}.csv")
    # Keep native Fig 3 temperatures; no extrapolation beyond the calculation.
    d = d[d.temperature_k.between(300, 750)].copy()
    lookup = {(r.type, round(r.N20, 6)): r.sample for r in samples.itertuples()}
    d["sample"] = [
        lookup[(t, round(n / 1e20, 6))]
        for t, n in zip(d.carrier_type, d.extrinsic_density_cm3, strict=False)  # noqa: E501
    ]
    d["observable"] = np.where(d.panel.isin(["a", "c"]), "S", "rho")
    d = d[(d.observable == "S") | (d.value > 0)].copy()
    d["y"] = d.value
    d.loc[d.observable == "rho", "y"] = 1000 / d.loc[d.observable == "rho", "value"]
    d["source"] = kind
    dsrc.append(d)
data = pd.concat(dsrc, ignore_index=True)
details = []
for (sample, kind, var), d in data.groupby(["sample", "source", "observable"]):  # noqa: B007
    d = d.copy()
    for gap in ["paper", "fixed300"]:
        m = model[(model["sample"] == sample) & (model.gap == gap)]
        pred = np.interp(d.temperature_k, m["T"], m[var])
        d[gap] = pred
        d[gap + "_error"] = pred - d.y if var == "S" else 100 * (pred / d.y - 1)
    details.append(d)
data = pd.concat(details)
data.to_csv(out / "compared-points.csv", index=False)
summary = (
    data.groupby(["source", "sample", "observable"])
    .agg(
        n=("y", "size"),
        Tmin=("temperature_k", "min"),
        Tmax=("temperature_k", "max"),
        MAE=("paper_error", lambda x: abs(x).mean()),
        p95=("paper_error", lambda x: abs(x).quantile(0.95)),
        peak_error=("paper_error", lambda x: abs(x).max()),
        fixed_MAE=("fixed300_error", lambda x: abs(x).mean()),
    )
    .reset_index()
)
summary.to_csv(out / "metrics.csv", index=False)
for var, unit in [("S", "S (µV/K)"), ("rho", "ρ (mΩ cm)")]:
    fig, axes = plt.subplots(3, 3, figsize=(12, 9))
    for ax, rec in zip(axes.flat, samples.itertuples(), strict=False):
        sub = model[model["sample"] == rec.sample]
        for gap, ls, col, label in [
            ("fixed300", "--", "#c26515", "Fixed gap, 0.22 eV"),
            ("paper", "-", "#176489", "SeeBand with published gap"),
        ]:
            m = sub[sub.gap == gap]
            ax.plot(m["T"], m[var], ls, color=col, lw=1.8, label=label)
        for kind, marker, col, label in [
            ("2PB", "x", "black", "Published 2PB curve"),
            ("data", "o", "#81778c", "Experimental symbols"),
        ]:
            d = data[
                (data["sample"] == rec.sample) & (data.observable == var) & (data.source == kind)
            ].sort_values("temperature_k")
            if kind == "2PB" and len(d):
                d = d.iloc[
                    np.unique(np.linspace(0, len(d) - 1, min(20, len(d))).round().astype(int))
                ]
            ax.scatter(
                d.temperature_k,
                d.y,
                s=17 if kind == "data" else 19,
                marker=marker,
                alpha=0.8,
                label=label,
                linewidth=0.8,
                color=col,
                zorder=3,
            )
        ax.set_title(f"{rec.composition}  ({rec.type})", fontsize=10)
        if var == "rho":
            ax.set_yscale("log")
        ax.grid(alpha=0.2)
        ax.set_xlim(295, 755)
    for ax in axes[-1]:
        ax.set_xlabel("Temperature (K)")
    for ax in axes[:, 0]:
        ax.set_ylabel(unit)
    fig.suptitle("Mg₂Sn  ·  " + unit + "  ·  fixed parameters from Tables 1–2", fontsize=15)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=9)
    fig.tight_layout(rect=[0, 0.05, 1, 0.96])
    fig.savefig(out / f"comparison-{var}.png", dpi=160)
print(summary.round(2).to_string(index=False))
