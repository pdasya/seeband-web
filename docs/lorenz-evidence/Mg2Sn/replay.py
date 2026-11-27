# ruff: noqa: T201 -- print replay results for reviewers.
"""Run with seeband_core 9929fb4 on PYTHONPATH; no free parameters."""

import csv
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import expit
from seeband_core import math_module as m
from seeband_core.explicit_transport import explicit_curves
from seeband_core.model_interface import ExplicitBands

out = Path(__file__).resolve().parent
md = np.array([1.1, 2.0])
N = np.array([2, 3])
D = np.array([9.5, 6.7])
mb = md / N ** (2 / 3)


def pref(T):
    thermal = m.kB * T
    dos = 4 * np.pi * (2 * md * m.me * thermal / m.h**2) ** 1.5
    mobility = (
        np.pi
        * np.sqrt(8)
        * m.hbar**4
        * m.e
        * 3590
        * 4800**2
        / (4 * (D * m.e) ** 2 * (mb * m.me) ** 2.5 * thermal**1.5)
    )
    return dos, mobility


dos, mobility = pref(300)
amp = dos * m.e * mobility * 2 / 3
params = {"m1": mb[0], "mass_ratio": mb[1] / mb[0], "A": amp[0], "B": (D[0] / D[1]) ** 2}
assert np.isclose(amp[1] / amp[0], N[1] / N[0] * params["B"] / params["mass_ratio"])


def reference(T, E, net):
    dos, mu = pref(T)

    def F(j, x):
        return quad(lambda u: 2 * u ** (2 * j + 1) * expit(x - u * u), 0, 14, epsabs=1e-15)[0]

    def etas(u):
        return np.array([-u, u - E * m.e / (m.kB * T)])

    def populations(u):
        return dos * np.array([F(0.5, x) for x in etas(u)])

    u = brentq(lambda u: np.diff(populations(u))[0] / 1e26 - net / 1e26, -60, 60)
    eta = etas(u)
    half = np.array([F(0.5, x) for x in eta])
    zero = np.logaddexp(0, eta)
    one = np.array([F(1, x) for x in eta])
    sigma = populations(u) * m.e * mu * (2 / 3) * zero / half
    S = np.array([1, -1]) * m.kB / m.e * (2 * one / zero - eta)
    return S @ sigma / sigma.sum() * 1e6, 1e5 / sigma.sum()


rows = []
err = []
for sample in csv.DictReader((out / "samples.csv").open()):
    net = float(sample["N20"]) * 1e26 * (1 if sample["type"] == "n" else -1)
    settings = ExplicitBands("vb_cb", net_electron_density_per_m3=net)
    for T in range(300, 751, 5):
        for gap, E in [("paper", 0.28 - 0.0002 * T), ("fixed300", 0.22)]:
            values = explicit_curves(
                settings,
                "dpb_s_rho",
                {**params, "band_offset_k": E * m.e / m.kB},
                np.array([float(T)]),
                "acPh",
                2,
                3,
            )
            S = values["seebeck_v_per_k"][0] * 1e6
            rho = values["resistivity_ohm_m"][0] * 1e5
            rows.append(
                dict(sample=sample["sample"], T=T, gap=gap, Eg_eV=E, S=S, rho=rho, sigma=1000 / rho)
            )
            if T in (300, 500, 750):
                s2, r2 = reference(T, E, net)
                err.append((abs(S - s2), abs(rho / r2 - 1)))
print(
    "A B mass_ratio",
    params,
    "max abs S in uV/K and relative rho errors vs independent Eqs 2–12",
    np.max(err, axis=0),
)
with (out / "predictions.csv").open("w") as f:
    w = csv.DictWriter(f, fieldnames=rows[0])
    w.writeheader()
    w.writerows(rows)
