# ruff: noqa: T201 -- print replay results for reviewers.
"""Three parabolic bands: Pei DOS masses with Thesberg intravalley acoustic scattering."""

import csv
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from seeband_core import math_module as mm
from seeband_core.fermi_integrals import fermi_integral
from seeband_core.transport import band_transport

out = Path(__file__).resolve().parent
N = np.array([4, 12, 4])
K = np.array([3.58, 1.0, 3.58])  # longitudinal to transverse mass
D = np.array([19.0, 9.5, 19.0])
sign = np.array([-1.0, -1.0, 1.0])


def point(T, p20, case):
    kT = mm.kB * T / mm.e
    ref49 = case in ("Pei_edges", "Pei_PB")
    edges = np.array([-(0.18 if ref49 else 0.09) - 0.0004 * T, -0.36, 0])
    base = np.array([0.36, 2.0, 0.3])
    beta = np.array([0.5, 0.0, 0.5])
    md = base * ((T / 300) ** beta if case == "Pei_PB" else (1 + beta * (T - 300) / T))
    # md is the whole-band density-of-states mass. For one ellipsoid:
    mb = md / N ** (2 / 3)
    mt = mb / K ** (1 / 3)
    mc = 3 / (2 / mt + 1 / (mt * K))

    def carriers(mu):
        eta = sign * (mu - edges) / kT
        fd = np.array([fermi_integral(0.5, value) for value in eta])
        return (2 * mm.me * mm.kB * T / mm.hbar**2) ** 1.5 / (2 * np.pi**2) * md**1.5 * fd / 1e6

    target = p20 * 1e20
    mu = brentq(lambda x: -sign @ carriers(x) - target, -2, 1, xtol=1e-14)
    populations = carriers(mu)
    assert abs(-sign @ populations / target - 1) < 1e-11
    eta = sign * (mu - edges) / kT
    f, s, l = (  # noqa: E741
        np.array(
            [
                band_transport(np.array([float(T)]), np.array([u]), sgn * m, 0.0)[:3]
                for u, sgn, m in zip(eta, sign, mb, strict=False)
            ]
        )
        .squeeze(-1)
        .T
    )
    # For intravalley ADP, per-valley final DOS cancels the initial DOS;
    # each of N valleys conducts, with angular velocity average set by mc.
    factor = 1 / (md * D**2) if case == "previous" else N / (mc * D**2)
    conductance = f * factor
    w = conductance / conductance.sum()
    wh = sum(w[:2])
    sh = w[:2] @ s[:2] / wh
    hh = w[0] * w[1] / wh * (s[0] - s[1]) ** 2
    bip = wh * w[2] * (sh - s[2]) ** 2
    total = w @ l + hh + bip
    assert abs(total - (w @ (l + s * s) - (w @ s) ** 2)) < 1e-19
    row = dict(
        case=case,
        p20=p20,
        T=T,
        mu_eV=mu,
        S_h_uVK=sh * 1e6,
        L_intra=w @ l * 1e8,
        L_hh=hh * 1e8,
        L_bip=bip * 1e8,
        L_total=total * 1e8,
    )
    for i, b in enumerate(["L", "Sigma", "C"]):
        row.update(
            {
                b + "_sigma_pct": w[i] * 100,
                b + "_density_cm3": populations[i],
                b + "_eta": eta[i],
                b + "_S_uVK": s[i] * 1e6,
            }
        )
    return row


if __name__ == "__main__":
    rows = [
        point(t, p, c)
        for c in ["previous", "valleys", "Pei_edges", "Pei_PB"]
        for p in [1.5, 2.0, 2.5]
        for t in range(300, 851, 5)
    ]
    with (out / "bands.csv").open("w") as fp:
        wr = csv.DictWriter(fp, fieldnames=rows[0])
        wr.writeheader()
        wr.writerows(rows)
    for r in rows:
        if r["T"] == 700:
            print(
                r["case"],
                r["p20"],
                *(
                    round(r[v], 5)
                    for v in [
                        "mu_eV",
                        "L_sigma_pct",
                        "Sigma_sigma_pct",
                        "C_sigma_pct",
                        "L_intra",
                        "L_hh",
                        "L_bip",
                        "L_total",
                    ]
                ),
            )
    for c in ["previous", "valleys", "Pei_edges", "Pei_PB"]:
        r = point(400, 2.4, c)
        print(
            "400 K Hall check",
            c,
            r["L_density_cm3"] / (r["L_density_cm3"] + r["Sigma_density_cm3"]),
            r["L_sigma_pct"] / (r["L_sigma_pct"] + r["Sigma_sigma_pct"]),
            r["L_eta"],
            r["Sigma_eta"],
        )
