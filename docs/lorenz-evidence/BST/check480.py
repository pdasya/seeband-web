# ruff: noqa: T201 -- print replay results for reviewers.
"""Table 1, Materials 10, 763. Isotropic intravalley ADP, fixed net acceptors."""

import numpy as np
from scipy.optimize import brentq
from seeband_core import math_module as m
from seeband_core.fermi_integrals import fermi_integral
from seeband_core.transport import band_transport

T = 480.0
N = np.array([6, 2])
for x, mdh, Dh, De, na in zip(
    [0, 0.0025, 0.005, 0.01, 0.015, 0.02],
    [1.30, 1.35, 1.41, 1.46, 1.47, 1.48],
    [14.9, 14.4, 13.6, 13.4, 12.3, 12.2],
    [13.8, 12.5, 11.5, 10.0, 9.1, 8.2],
    [2.47, 3.53, 4.96, 6.60, 8.76, 11.96],
    strict=False,
):
    md = np.array([mdh, 0.84])
    mb = md / N ** (2 / 3)
    dos = 4 * np.pi * (2 * md * m.me * m.kB * T / m.h**2) ** 1.5

    def eta(mu):
        return np.array([-mu, mu - 0.145]) * m.e / (m.kB * T)

    def balance(mu):
        ph, ne = dos * np.array([fermi_integral(0.5, v) for v in eta(mu)])  # noqa: B023
        return (ph - ne) / 1e25 - na  # noqa: B023

    mu = brentq(balance, -1, 1)
    mobility = (
        np.pi
        * np.sqrt(8)
        * m.hbar**4
        * m.e
        * 54.7e9
        / (4 * (np.array([Dh, De]) * m.e) ** 2 * (mb * m.me) ** 2.5 * (m.kB * T) ** 1.5)
    )
    f, s, l, _ = (  # noqa: E741
        np.array(
            [
                band_transport(np.array([T]), np.array([v]), sign * mass, 0.0)
                for v, sign, mass in zip(eta(mu), [-1, 1], mb, strict=False)
            ]
        )
        .squeeze(-1)
        .T
    )
    sig = dos * m.e * mobility * 2 / 3 * f
    w = sig / sum(sig)
    bp = np.prod(w) * (s[0] - s[1]) ** 2
    print(
        f"{x:.4f},{mu:.6f},{sum(sig):.4f},{bp * sum(sig) * T:.4f},{bp * 1e8:.4f},{(w @ l + bp) * 1e8:.4f}"  # noqa: E501
    )
