# ruff: noqa: T201 -- print replay results for reviewers.
"""Reproduce positive Hall factors for holes from Pei et al. Eqs. 2 and 6."""

import csv
from pathlib import Path

import numpy as np
from scipy import constants
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import expit, roots_legendre

here = Path(__file__).resolve().parent
T = 400
alpha = constants.k * T / constants.e / (0.18 + 0.0004 * T)


def hall(eta, beta, K):
    def integrand(u, m, n):
        x = u * u
        g = x * (1 + beta * x)
        v = (1 + 2 * beta * x) ** 2 + 2
        return 2 * u * expit(x - eta) * expit(eta - x) * g**m / v**n

    def integrate(m, n):
        i = quad(integrand, 0, 12, args=(m, n), epsabs=1e-13, epsrel=1e-13)[0]
        z, w = roots_legendre(120)
        j = 6 * (w @ integrand(6 * (z + 1), m, n))
        assert abs(i - j) < 1e-12 * abs(i)
        return i

    geom = 3 * K * (K + 2) / (2 * K + 1) ** 2
    energy = integrate(0.5, 2) * integrate(1.5, 0) / integrate(1, 1) ** 2
    return geom, energy, geom * energy


def spb_reference(eta):
    def F(j):
        return quad(lambda u: 2 * u ** (2 * j + 1) * expit(eta - u * u), 0, 12)[0]

    return 0.75 * F(0.5) * F(-0.5) / np.logaddexp(0, eta) ** 2


a = hall(1.9, alpha, 3.58)[2]
s = hall(1.3, 0, 1)[2]
print("alpha", alpha)
for eta in [1.5, 1.9, 2, 2.5]:
    print("L", eta, hall(eta, alpha, 3.58))
for eta in [1, 1.3, 1.5, 2]:
    print("Sigma", eta, hall(eta, 0, 1))
    assert abs(hall(eta, 0, 1)[2] - spb_reference(eta)) < 1e-11


def h(f, b):
    return (a * b * b * f + s * (1 - f)) / (1 + (b - 1) * f) ** 2


def station(b):
    return 1 / (b - 1) - 2 * s / (a * b * b - s)


with (here / "figure/pei-si-s3a-summary.csv").open() as file:
    data = {
        r["feature"]: float(r["hall_cm3_per_c"])
        for r in csv.DictReader(file)
        if r["sample"] == "PbTe"
    }
peak, low = data["peak"], data["lowest_temperature"]
for p in [2.4e20, 0.9 / (constants.e * low)]:
    target = p * constants.e * peak
    b = brentq(lambda b: h(station(b), b) - target, 2, 15)  # noqa: B023
    print("p, target, stationary b, fL, fSigma", p, target, b, station(b), 1 - station(b))
print(
    "b=4: fL, RH at nominal p",
    [(f, h(f, 4) / (constants.e * 2.4e20)) for f in [0.77, 0.23, station(4)]],
)
q, w = 0.825676, 0.474744
print(
    "nearest S3(b), H, R",
    H := (a * (1 - w) ** 2 / (1 - q) + s * w * w / q),
    H / (constants.e * 2.5e20),
)
