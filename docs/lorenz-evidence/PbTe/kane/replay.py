# ruff: noqa: T201 -- print replay results for reviewers.
"""Run with Python, numpy, scipy, pandas and matplotlib from this directory."""

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from scipy import constants as c
from scipy.optimize import brentq
from scipy.special import expit, roots_legendre

matplotlib.use("Agg")
import matplotlib.pyplot as plt

out = Path(__file__).resolve().parent
N = np.array([4, 12, 4])
K = np.array([3.58, 1, 3.58])
D = np.array([19, 9.5, 19])
charge = np.array([1, 1, -1])
k = c.k / c.e


def quadrature(n):
    # x = u^2 regularizes the DOS endpoint.
    z, w = roots_legendre(n)
    u = 5 * (1 + z)
    return u * u, 10 * u * w


def point(T, p, grid, kane=True):
    x, dx = grid
    gap = 0.18 + 0.0004 * T
    edge = np.array([-gap, -0.36, 0])
    md = np.array([0.36, 2.0, 0.30]) * (T / 300) ** np.array([0.5, 0, 0.5])
    alpha = np.array([1.0, 0, 1]) * k * T / gap * kane
    m_trans = md / N ** (2 / 3) / K ** (1 / 3)
    mc = 3 * m_trans / (2 + 1 / K)
    gamma = x + alpha[:, None] * x * x
    pref = (2 * c.m_e * c.k * T / c.hbar**2) ** 1.5 / (3 * np.pi**2) * md**1.5 / 1e6

    def weights(mu):
        eta = charge * (edge - mu) / (k * T)
        v = x - eta[:, None]
        return dx * expit(v) * expit(-v), v

    def density(mu):
        return pref * (weights(mu)[0] * gamma**1.5).sum(axis=1)

    mu = brentq(lambda mu: charge @ density(mu) / (p * 1e20) - 1, -0.7, 0, xtol=1e-14)
    assert abs(charge @ density(mu) / (p * 1e20) - 1) < 1e-10
    df, v = weights(mu)
    kernel = 3 * gamma / ((1 + 2 * alpha[:, None] * x) ** 2 + 2)
    transport = (N / (mc * D**2))[:, None] * df * kernel
    g = transport.sum(axis=1)
    w = g / sum(g)
    moment = (transport * v).sum(axis=1) / g
    S = charge * k * moment
    intra = (w * k**2) @ ((transport * (v - moment[:, None]) ** 2).sum(axis=1) / g)
    hh = w[0] * w[1] / sum(w[:2]) * (S[0] - S[1]) ** 2
    bip = sum(w[:2]) * w[2] * (w[:2] @ S[:2] / sum(w[:2]) - S[2]) ** 2
    total = intra + hh + bip
    direct = (transport * (charge[:, None] * k * v - w @ S) ** 2).sum() / sum(g)
    assert abs(direct / total - 1) < 1e-12
    return dict(
        T=T,
        p20=p,
        mu_eV=mu,
        wL=w[0],
        wSigma=w[1],
        wC=w[2],
        pSigma_fraction=density(mu)[1] / sum(density(mu)[:2]),
        intra=intra * 1e8,
        hh=hh * 1e8,
        bip=bip * 1e8,
        total=total * 1e8,
    )


if __name__ == "__main__":
    grid = quadrature(180)
    fine = quadrature(320)
    fractions = pd.read_csv(out.parent / "ref49/inset/fractions_1K.csv")
    reference = pd.read_csv(out.parent / "reference.csv")
    rows = []
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), layout="constrained")
    for p, color in zip((1.5, 2, 2.5), ("#177945", "#2474aa", "#b03847"), strict=False):
        block = pd.DataFrame(point(t, p, grid) for t in range(300, 851, 5))
        for col in ("wSigma", "total", "mu_eV"):
            fine_values = [point(t, p, fine)[col] for t in block["T"]]
            assert np.max(abs(block[col] - fine_values)) < 1e-9
        inset = fractions[
            (fractions.concentration_cm3 == p * 1e20)
            & (fractions.quantity == "sigma_sigma_over_sigma_total")
        ].sort_values("temperature_k")
        paper = reference[
            (reference.p_cm3 == p * 1e20) & (reference["style"] == "solid")
        ].sort_values("temperature_k")
        block["wSigma_Pei"] = np.interp(block["T"], inset.temperature_k, inset.fraction)
        block["total_Thesberg"] = np.interp(
            block["T"], paper.temperature_k, paper.lorenz_1e8_w_ohm_k2
        )
        print(block[block["T"] == 700].round(6).to_string(index=False))
        print(
            "RMS and max abs difference (pp)",
            100 * np.sqrt(np.mean((block.wSigma - block.wSigma_Pei) ** 2)),
            100 * max(abs(block.wSigma - block.wSigma_Pei)),
        )
        for ax, calc, ref, factor in zip(
            axes, ["wSigma", "total"], ["wSigma_Pei", "total_Thesberg"], [100, 1], strict=False
        ):
            ax.plot(block["T"], factor * block[calc], color=color, label=f"{p:.1f}")
            ax.plot(block["T"], factor * block[ref], color=color, ls="--")
        rows.append(block)
    for ax, title, ylabel in zip(
        axes,
        ["Heavy-hole conductivity share", "Open-circuit Lorenz number"],
        ["σΣ / σ (%)", "L (10⁻⁸ W Ω K⁻²)"],
        strict=False,
    ):
        ax.set(xlabel="Temperature (K)", ylabel=ylabel, title=title)
        ax.axvline(700, color="0.6", lw=0.8)
        ax.grid(alpha=0.2)
    axes[0].legend(title="Net holes (10²⁰ cm⁻³)")
    fig.suptitle("PbTe   |   solid: Kane L/C + parabolic Σ     dashed: Pei S3(b) / Thesberg Fig. 6")
    fig.savefig(out / "comparison.png", dpi=175)
    pd.concat(rows).to_csv(out / "curves.csv", index=False)
