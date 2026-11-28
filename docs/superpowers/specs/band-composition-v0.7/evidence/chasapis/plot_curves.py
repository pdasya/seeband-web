"""Render the six measured curves and the two constant-prefactor predictions."""

import csv
from pathlib import Path

import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent


def main():
    with (HERE / "curves.csv").open() as f:
        rows = list(csv.DictReader(f))
    fig, axes = plt.subplots(2, 3, figsize=(10.8, 5.7), sharex=True, layout="constrained")
    for j, x in enumerate(("0.01", "0.02", "0.03")):
        for i, observable in enumerate(("S", "Hall")):
            ax = axes[i, j]
            data = [r for r in rows if r["composition"] == x and r["observable"] == observable]
            for case, label, color, style in (
                ("paper", "Constant weight, moving bands", "#0072B2", "-"),
                ("fixed", "Constant weight, fixed bands", "#D55E00", "--"),
            ):
                points = sorted(
                    (r for r in data if r["structure"] == case),
                    key=lambda r: float(r["temperature_k"]),
                )
                t = [float(r["temperature_k"]) for r in points]
                ax.plot(
                    t,
                    [float(r["constant_w2"]) for r in points],
                    style,
                    color=color,
                    label=label,
                    linewidth=1.8,
                )
                if case == "paper":
                    ax.scatter(
                        t,
                        [float(r["observed"]) for r in points],
                        s=16,
                        marker="o",
                        facecolors="none",
                        edgecolors="black",
                        linewidths=0.9,
                        label="Digitized measurements",
                        zorder=5,
                    )
                    subset = [r for r in points if r["published_f0_interpolated"]]
                    ax.plot(
                        [float(r["temperature_k"]) for r in subset],
                        [float(r["published_f0_interpolated"]) for r in subset],
                        ":",
                        color="#008060",
                        linewidth=1.8,
                        label="Published $f_0(T)$, moving bands",
                    )
            if i == 0:
                ax.set_title(f"Na fraction x = {x}")
            else:
                ax.set_xlabel("Temperature (K)")
            if j == 0:
                ax.set_ylabel("Seebeck (μV/K)" if i == 0 else "Hall coefficient (cm³/C)")
            ax.grid(alpha=0.18)
            ax.spines[["top", "right"]].set_visible(False)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=2, frameon=False, loc="outside lower center")
    fig.savefig(HERE / "curves.png", dpi=165)


if __name__ == "__main__":
    main()
