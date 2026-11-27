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


def state(ef):
    eta = q * (edge - ef) / (c.k * T / c.e)
    j, h = np.array([moments(mu, a) for mu, a in zip(eta, alpha, strict=False)]).T
    n = N * (2 * mb * c.m_e * c.k * T) ** 1.5 * h / (3 * np.pi**2 * c.hbar**3) / 1e6
    return j / h, n, eta


def calc(p20):
    ef = brentq(lambda ef: q @ state(ef)[1] / 1e20 - p20, -0.6, -0.2)
    r, n, eta = state(ef)
    mu = (
        1e4
        * 2
        * np.pi
        * c.hbar**4
        * c.e
        * elastic
        * r
        / (mc * c.m_e * (2 * mb * c.m_e * c.k * T) ** 1.5 * (D * c.e) ** 2)
    )
    sigma = c.e * n * mu  # S/cm
    return eta, r, mu, sigma, mu[0] / mu[1]


print("density kg/m3, Cl Pa, mb, mc", mass_density, elastic, mb, mc)
for p in (2.4, 2.5):
    eta, r, mu, sigma, b = calc(p)
    pref = (mc[1] / mc[0]) * (mb[1] / mb[0]) ** 1.5 * r[0] / r[1]
    assert abs(b - pref * (D[1] / D[0]) ** 2) < 1e-10
    print(
        "p20,eta,moment_ratio,mobilities cm2/Vs, rho mOhm cm, b, kinetic ratio",
        p,
        eta,
        r,
        mu,
        1e3 / sum(sigma),
        b,
        pref,
    )
    for target in (4, 5.2, 5.2403949073):
        print(
            "target b, D_S/D_L required, D_S if L=19, D_L if S=9.5",
            target,
            (target / pref) ** 0.5,
            19 * (target / pref) ** 0.5,
            9.5 / (target / pref) ** 0.5,
        )
q_sig = 0.825676
w_sig = 0.474744
p = 2.5e20
b = q_sig * (1 - w_sig) / ((1 - q_sig) * w_sig)
print(
    "Fig. S3b at p20=2.5; inferred b, mu_i times rho[mOhm cm]",
    b,
    1e3 / (c.e * p) * np.array([(1 - w_sig) / (1 - q_sig), w_sig / q_sig]),
)
mob = calc(2.5)[2][:2]
rel = 1e3 / (c.e * p) * np.array([(1 - w_sig) / (1 - q_sig), w_sig / q_sig])
print("Required independent rho[mOhm cm] for published D for each band, same fractions:", rel / mob)
print(
    "Quoted reduced potentials 1.9,1.3: b",
    (mc[1] / mc[0])
    * (mb[1] / mb[0]) ** 1.5
    * 0.25
    * np.divide(*[np.divide(*moments(z, a)) for z, a in zip([1.9, 1.3], alpha, strict=False)]),
)

print("400 K sensitivity to valley normalization at fixed D, masses and fillings")
print("Scenario names describe only masses in mobility, density calculation stays the same.")
p20 = 2.4
eta, r, mu, _, b = calc(p20)
mass_cases = {
    "pocket": np.ones(2),
    "family DOS used only in acoustic final-state count": 1 / N[:2],
    "family masses in both factors, retaining K": 1 / N[:2] ** (5 / 3),
    "family masses as isotropic scalar (K ignored in inertia)": (mc[:2] / md[:2]) / N[:2],
}
for name, scale in mass_cases.items():
    m = mu[:2] * scale
    print(name, "mu, b", m, m[0] / m[1])
    if "scalar" in name or "both factors" in name:
        m = m * (D[:2] / np.array([12.0, 4.5])) ** 2
        print("  sensitivity using patent D (other assumptions held): b=", m[0] / m[1])

print("400 K mass and filling factors", mc[1] / mc[0], (mb[1] / mb[0]) ** 1.5, r[0] / r[1])

from csv import DictReader  # noqa: E402

with (Path(__file__).parent / "resistivity/rho400.csv").open() as f:
    observation = next(DictReader(f))
rho_milliohm = float(observation["rho_milliohm_cm"])
print("Rho, mOhm cm", rho_milliohm)
for case, p, b, fL in [
    ("SI literal 400K", 2.4, 4, 0.77),
    ("SI with complementary f", 2.4, 4, 0.23),
    ("S1 normalized by measured low T", 2.330854, 5.2034976, 0.1679054),
    ("S1 nominal sample", 2.4, 5.4273455, 0.1617131),
    ("S3(b) adjacent density", 2.5, 5.2403949, 1 - 0.825676),
]:
    mu_s = 1 / (c.e * p * 1e20 * rho_milliohm * 1e-3 * (1 + (b - 1) * fL))
    mu_obs = np.array([b * mu_s, mu_s])
    model = calc(p)[2][:2]
    effective = D[:2] * np.sqrt(model / mu_obs)
    assert np.allclose(model * (D[:2] / effective) ** 2, mu_obs, rtol=1e-13)
    print(
        case,
        " mobilities, inverted eV, implied D_S/D_L",
        mu_obs,
        effective,
        effective[1] / effective[0],
    )
