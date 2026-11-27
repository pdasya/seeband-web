# ruff: noqa: T201 -- print replay results for reviewers.
"""Independent Landauer energy integral using a common electron-energy axis.
Replay with SciPy, NumPy and the included density-scenario seeband.csv.
"""

import csv
from pathlib import Path

import numpy as np
from scipy.constants import Boltzmann as kb
from scipy.constants import electron_mass as me
from scipy.constants import elementary_charge as e
from scipy.constants import hbar
from scipy.integrate import quad_vec
from scipy.optimize import brentq
from scipy.special import expit, roots_legendre

out = Path(__file__).resolve().parent
z, weights = roots_legendre(200)
# Infinite upper limit approximated at kinetic energy 100 kBT for carrier counts.
u = 5 * (z + 1)
weights = 10 * u * weights
x = u * u
sign = np.array([-1, -1, 1])


def bands(t):
    return np.array([-(0.09 + 0.0004 * t), -0.36, 0]), np.array([0.36, 2.0, 0.30]) * (
        1 + np.array([0.5, 0, 0.5]) * (t - 300) / t
    )


def holes(t, mu):
    edge, m = bands(t)
    eta = sign * (mu - edge) / (kb * t / e)
    n = (
        (2 * me * kb * t / hbar**2) ** 1.5
        / (2 * np.pi**2)
        / 1e6
        * m**1.5
        * ((expit(eta[:, None] - x) * np.sqrt(x)) @ weights)
    )
    return -sign @ n


def direct(t, p):
    edge, m = bands(t)
    kt = kb * t / e
    mu = brentq(lambda mu: holes(t, mu) / 1e20 - p, -1, 0.5, xtol=1e-14)
    threshold = (edge - mu) / kt
    amplitude = 1 / (m * np.array([19.0, 9.5, 19.0]) ** 2)

    # z is signed (electron energy - mu) / kBT for all three bands.
    def integrand(z):
        kernel = amplitude @ np.maximum(sign * (z - threshold), 0.0)
        return kernel * expit(z) * expit(-z) * np.array([1.0, z, z * z])

    j = quad_vec(integrand, -100, 100, points=threshold, epsabs=1e-13, epsrel=1e-12)[0]
    return mu, (kb / e) ** 2 * (j[2] / j[0] - (j[1] / j[0]) ** 2) * 1e8


with (out.parent / "seeband.csv").open() as f:
    rows = [r for r in csv.DictReader(f) if r["scenario"] == "density"]


def compare():
    errors = []
    for r in rows:
        mu, lorenz = direct(float(r["T_K"]), float(r["p20"]))
        errors.append([abs(mu - float(r["mu_eV"])), abs(lorenz - float(r["total"]))])
    print(len(errors), "points; max delta mu (eV), L (1e-8 units):", np.max(errors, axis=0))
    return np.max(errors, axis=0)


print("SciPy constants")
compare()
# CODATA values used by the pinned comparison kernel.
from math import pi  # noqa: E402

kb = 1.38064852e-23  # noqa: F811
me = 9.1093837e-31  # noqa: F811
hbar = 6.62607015e-34 / (2 * pi)  # noqa: F811
print("Matched core constants")
assert compare()[1] < 1e-8
with (out / "inverse.csv").open() as f:
    for r in csv.DictReader(f):
        t = float(r["T"])
        mu = float(r["fig5_inferred_mu_eV"])
        print(
            "T, label p20, inferred EF (eV), net p20 with printed scalar model",
            t,
            r["p20"],
            mu,
            holes(t, mu) / 1e20,
        )
