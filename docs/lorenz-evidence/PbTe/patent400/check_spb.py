# ruff: noqa: T201 -- print replay results for reviewers.
"""Use seeband-web core from revision 9929fb4 via PYTHONPATH."""

import csv
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.special import expit
from seeband_core import math_module as mm
from seeband_core.transport import band_transport

eta = np.linspace(-5, 12, 69)
T = np.full(len(eta), 300.0)
_, S, L, _ = band_transport(T, eta, 1.0, 0.0)
kim = (1.5 + np.exp(-np.abs(S) * 1e6 / 116)) * 1e-8
_, Sii, _, _ = band_transport(T, eta, 1.0, 2.0)


def f(j, u):
    return quad(lambda x: x**j * expit(u - x), 0, np.inf)[0]


kii = -mm.kB / mm.e * np.array([4 * f(3, u) / (3 * f(2, u)) - u for u in eta])
print(
    "Kim 2015 max relative difference, using exact core value as denominator", max(abs(kim / L - 1))
)
print("Kim & Kim 2021 II Table 1 max |delta S| in microV/K", max(abs(Sii - kii)) * 1e6)
with (Path(__file__).parent / "spb.csv").open("w") as fp:
    writer = csv.writer(fp)
    writer.writerow(
        ["eta", "ac_S_uV_K", "ac_L_1e8", "Kim_2015_L_1e8", "ion_S_uV_K", "Kim_2021_ion_S_uV_K"]
    )
    writer.writerows(zip(eta, 1e6 * S, 1e8 * L, 1e8 * kim, 1e6 * Sii, 1e6 * kii, strict=False))
