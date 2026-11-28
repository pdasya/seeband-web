"""Run with SeeBand core installed (tested at 8c6fafc). Output L in 1e-8 W ohm/K²."""

import csv
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from seeband_core import math_module as mm
from seeband_core.fermi_integrals import fermi_integral
from seeband_core.transport import band_transport

OUT = Path(__file__).resolve().parent
# Values read from the lines in Fig. 5(c); see digitization.
MARKS = {1.5: -0.22010948382382572, 2.0: -0.246073511954614, 2.5: -0.2659729616223998}
D = np.array([19.0, 9.5, 19.0])  # L valence, Sigma valence, C
SIGNS = np.array([-1.0, -1.0, 1.0])
BANDS = ["L", "Sigma", "C"]
KB_EV = mm.kB / mm.e


def evaluate(T, p20, scenario):
    edges = np.array([-(0.09 + 0.0004 * T), -0.36, 0.0])
    masses = np.array([0.36, 2.0, 0.3]) * (1 + np.array([0.5, 0, 0.5]) * (T - 300) / T)
    N = np.array([4, 12, 4]) if scenario == "density_valleys" else np.ones(3)

    def eta(mu):
        return SIGNS * (mu - edges) / (KB_EV * T)

    def net_holes(mu):
        # 3D DOS, both spin states; unnormalised F_{1/2}; result in cm^-3.
        factor = (2 * mm.me * mm.kB * T / mm.hbar**2) ** 1.5 / (2 * np.pi**2) / 1e6
        populations = factor * N * masses**1.5 * np.array([fermi_integral(0.5, x) for x in eta(mu)])
        return -SIGNS @ populations

    mu = (
        MARKS[p20]
        if scenario == "figure_mark"
        else brentq(lambda x: net_holes(x) - p20 * 1e20, -2, 1, xtol=1e-14)
    )
    f, s, l = (  # noqa: E741
        np.array(
            [
                band_transport(np.array([float(T)]), np.array([x]), sign * m, 0.0)[:3]
                for x, sign, m in zip(eta(mu), SIGNS, masses, strict=False)
            ]
        )
        .squeeze(-1)
        .T
    )
    conductance = N * f / (masses * D**2)  # common factor cancels in normalized weights
    w = conductance / conductance.sum()
    wh = w[0] + w[1]
    sh = w[:2] @ s[:2] / wh
    hh = w[0] * w[1] / wh * (s[0] - s[1]) ** 2
    bip = wh * w[2] * (sh - s[2]) ** 2
    intrinsic = w @ l
    total = intrinsic + hh + bip
    # Independent assembly using total first and second moments.
    assert np.isclose(total, w @ (l + s * s) - (w @ s) ** 2, rtol=1e-12, atol=1e-21)
    row = dict(scenario=scenario, p20=p20, T_K=T, mu_eV=mu, net_holes_cm3=net_holes(mu))
    for i, name in enumerate(BANDS):
        row.update(
            {
                name + "_fraction": w[i],
                name + "_S_uVK": s[i] * 1e6,
                name + "_own_L": l[i] * 1e8,
                name + "_weighted_L": w[i] * l[i] * 1e8,
            }
        )
    row.update(intraband=intrinsic * 1e8, hole_hole=hh * 1e8, bipolar=bip * 1e8, total=total * 1e8)
    return row


if __name__ == "__main__":
    rows = [
        evaluate(t, p, variant)
        for variant in ("figure_mark", "density", "density_valleys")
        for p in MARKS
        for t in range(300, 851, 5)
    ]
    with (OUT / "seeband.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
