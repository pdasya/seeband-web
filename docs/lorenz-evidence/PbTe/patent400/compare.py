# ruff: noqa: T201 -- print replay results for reviewers.
"""400 K PbTe. Drift mobilities from Pei et al. Eq. 3 divided by the Hall factor."""

from pathlib import Path

import numpy as np
from scipy import constants as c
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import expit

T = 400.0
K = np.array([3.58, 1.0, 3.58])
N = np.array([4.0, 12.0, 4.0])
md = np.array([0.36, 2.0, 0.30]) * (T / 300) ** np.array([0.5, 0, 0.5])
mb = md / N ** (2 / 3)
mc = 3 * mb / (K ** (1 / 3) * (2 + 1 / K))
D = np.array([19.0, 9.5, 19.0])
gap = 0.18 + 0.0004 * T
alpha = np.array([1.0, 0.0, 1.0]) * c.k * T / (gap * c.e)
edge = np.array([-gap, -0.36, 0])
q = np.array([1.0, 1.0, -1.0])
# Normalize the absolute mobilities using v_long from SI p.3 and the
# ideal rock-salt density from a=6.46 Angstrom in SI p.4, four PbTe per cell.
mass_density = 4 * (207.2 + 127.60) * c.atomic_mass / (6.46e-10) ** 3
elastic = mass_density * 3600**2


def moments(eta, beta):
    def integrand(u, transport):
        x = u * u
        g = x * (1 + beta * x)
        moment = 3 * g / ((1 + 2 * beta * x) ** 2 + 2) if transport else g**1.5
        return 2 * u * expit(x - eta) * expit(eta - x) * moment

    return np.array([quad(integrand, 0, 12, args=(t,), epsabs=1e-13)[0] for t in (True, False)])


import csv  # noqa: E402

from scipy.special import roots_legendre  # noqa: E402

out = Path(__file__).resolve().parent
cases = [
    ("Nature D, pocket masses", D, mb, mc),
    ("patent D, scalar single-band masses", np.array([12.0, 4.5, 12.0]), md, md),
    (
        "patent D, anisotropic single-band masses",
        np.array([12.0, 4.5, 12.0]),
        md,
        3 * md / (K ** (1 / 3) * (2 + 1 / K)),
    ),
]
rows = []
for p20 in [1.5, 2.0, 2.330854, 2.4, 2.5]:
    for name, deformation, scattmass, inertia in cases:
        is_patent = name.startswith("patent")
        # The patent counts a family as a single effective band. Spin is already in the DOS.
        degeneracy = np.ones(3) if is_patent else N
        dos_mass = md if is_patent else mb

        def state(ef):
            eta = q * (edge - ef) / (c.k * T / c.e)
            J, H = np.array([moments(z, a) for z, a in zip(eta, alpha, strict=False)]).T
            pop = (
                degeneracy  # noqa: B023
                * (2 * dos_mass * c.m_e * c.k * T) ** 1.5  # noqa: B023
                * H
                / (3 * np.pi**2 * c.hbar**3)
                / 1e6
            )
            return J / H, pop, eta

        def constraint(ef):
            pop = state(ef)[1]
            return (sum(pop[:2]) if is_patent else q @ pop) / 1e20 - p20  # noqa: B023

        ef = brentq(constraint, -0.6, -0.2, xtol=1e-14)
        ratio, pop, eta = state(ef)
        assert abs(constraint(ef)) < 1e-10
        z, w = roots_legendre(160)
        u = 6 * (z + 1)
        for i in range(3):
            x = u * u
            window = 12 * u * w * expit(x - eta[i]) * expit(eta[i] - x)
            Y = x * (1 + alpha[i] * x)
            H = window @ Y**1.5
            J = window @ (3 * Y / ((1 + 2 * alpha[i] * x) ** 2 + 2))
            assert np.isclose(J / H, ratio[i], rtol=1e-11)
            assert np.isclose(
                (2 * md[i] * c.m_e * c.k * T) ** 1.5 * H / (3 * np.pi**2 * c.hbar**3) / 1e6,
                pop[i],
                rtol=1e-11,
            )
        mobility = (
            1e4
            * 2
            * np.pi
            * c.hbar**4
            * c.e
            * elastic
            * ratio
            / (
                inertia
                * c.m_e
                * (2 * scattmass * c.m_e * c.k * T) ** 1.5
                * (deformation * c.e) ** 2
            )
        )
        sigma = c.e * pop * mobility
        rows.append(
            dict(
                case=name,
                p20=p20,
                ef_eV=ef,
                eta_L=eta[0],
                eta_Sigma=eta[1],
                mu_L=mobility[0],
                mu_Sigma=mobility[1],
                b=mobility[0] / mobility[1],
                rho_mOhm_cm=1e3 / sigma.sum(),
                fraction_Sigma=sigma[1] / sigma.sum(),
            )
        )
        if p20 in (2.4, 2.5):
            print(rows[-1])
with (out / "comparison.csv").open("w") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0])
    writer.writeheader()
    writer.writerows(rows)
