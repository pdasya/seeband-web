"""Infer mu solely from the published Sigma hole fraction and its parabolic DOS.
p on the figure is interpreted as total holes, as in Pei Fig. 2.
"""

import csv
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from seeband_core import math_module as mm
from seeband_core.fermi_integrals import fermi_integral

out = Path(__file__).resolve().parent
with (out / "inset/fractions_1K.csv").open() as f:
    rows = list(csv.DictReader(f))
indexed = {
    (r["temperature_k"], r["concentration_cm3"], r["quantity"]): float(r["fraction"]) for r in rows
}
data = []
for (t, p, q), frac in indexed.items():
    if q != "p_sigma_over_p_total":
        continue
    p_key = p
    T = float(t)
    p = float(p)
    pref = (2 * 2 * mm.me * mm.kB * T / mm.hbar**2) ** 1.5 / (2 * np.pi**2) * 1e-6
    eta = brentq(lambda v: pref * fermi_integral(0.5, v) / p - frac, -50, 50)  # noqa: B023
    sigmafrac = indexed[(t, p_key, "sigma_sigma_over_sigma_total")]
    data.append(
        dict(
            T=T,
            p20=p / 1e20,
            mu_from_Sigma_eV=-0.36 - eta * mm.kB * T / mm.e,
            Sigma_population_fraction=frac,
            Sigma_sigma_pct=sigmafrac * 100,
        )
    )
with (out / "published-and-inferred.csv").open("w") as f:
    w = csv.DictWriter(f, fieldnames=data[0])
    w.writeheader()
    w.writerows(data)
