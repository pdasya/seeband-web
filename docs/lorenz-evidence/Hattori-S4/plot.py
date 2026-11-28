from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

root = Path(__file__).resolve().parent
data = pd.read_csv(root / "comparison.csv")
model = pd.read_csv(root / "model.csv")
series = [
    ("sigma", "sigma", "σ (S/m)"),
    ("seebeck", "S", "S (μV/K)"),
    ("kappa_el", "kappa", "κₑₗ (W/m K)"),
    ("L", "L", "L (10⁻⁸ W Ω/K²)"),
]


def panel(ax, delta, q, m, label):
    p = data[(data.delta_e_ev == delta) & (data.quantity == q)].sort_values("mu_ev")
    y = model[(model.offset_eV == delta) & model.mu_eV.between(-0.75, 0.60)]
    upper = 4.5 if q == "L" else 1.12 * max(y[m].max(), p.upper.max())
    ax.set_ylim(0, upper)
    finite = p.upper.notna()
    ax.fill_between(
        p.mu_ev.to_numpy(),
        p.lower.clip(0, upper).to_numpy(),
        p.upper.clip(0, upper).to_numpy(),
        where=finite.to_numpy(),
        color="#e1b673",
        alpha=0.48,
    )
    bad = p[~finite]
    if len(bad):
        ax.plot(bad.mu_ev, np.full(len(bad), 0.98 * upper), "|", color="#a6957a", ms=4)
    r = p[p.trace_center.notna()]
    ax.scatter(r.mu_ev, r.trace_center, s=10, color="#973d19", zorder=3)
    ax.plot(y.mu_eV, y[m], color="#104d7d", lw=1.7)
    ax.set(xlim=(-0.755, 0.605), ylabel=label, xlabel="μ (eV)")
    ax.grid(alpha=0.18)


def caption(fig):
    fig.text(
        0.5,
        0.014,
        "Blue — SeeBand     • native figure reading     Shading — reading interval     Top ticks — unbounded L interval",  # noqa: E501
        ha="center",
        fontsize=8,
    )


with PdfPages(root / "all-offsets.pdf") as pdf:
    for delta in sorted(model.offset_eV.unique()):
        fig, axes = plt.subplots(2, 2, figsize=(9, 7))
        for ax, col in zip(axes.flat, series, strict=False):
            panel(ax, delta, *col)
        fig.suptitle(f"Hattori S4d–f   |   ΔE = {delta:+.1f} eV   |   T = 900 K")
        caption(fig)
        fig.tight_layout(rect=(0, 0.045, 1, 0.95))
        pdf.savefig(fig)
        plt.close(fig)
fig, axes = plt.subplots(4, 3, figsize=(12, 10))
for col, delta in enumerate([-0.3, 0, 0.3]):
    for ax, spec in zip(axes[:, col], series, strict=False):
        panel(ax, delta, *spec)
    axes[0, col].set_title(f"ΔE = {delta:+.1f} eV")
caption(fig)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(root / "overview.png", dpi=140)
plt.close(fig)
