#!/usr/bin/env python3
"""Synthetic acPh+dis design evidence for 1–3 isotropic spin-2 parabolas.

Run: .venv/bin/python scripts/verify_mixed_scattering_design.py
Optional retained-P18 comparison (not exposed explicit_curves support):
  PYTHONPATH=packages/seeband_core/src .venv/bin/python \
      scripts/verify_mixed_scattering_design.py --legacy
Requires installed NumPy/SciPy. No production imports without --legacy.

q=-s*e; s=+1 CB/-1 VB; edges and mu in K (energy/kB), masses in m_e,
N excludes spin. Synthetic EF(0) sets fixed D=n-p; solve one mu(T).
Gamma_ac=(1/tau_ref)*sqrt(u/(kB*300K))*T/300K;
Gamma_dis=(1/tau_ref)*sqrt(u/(kB*300K))*c/300K. c>=0 is in K.
Matthiessen: tau=1/(a*Gamma_ac+d*Gamma_dis), with a,d>=0, not both zero.
Hence sigma_i=A*w_i*T/(a*T+d*c_i)*F0(eta_i), w_i=(Ni/N1)*b_i/(mi/m1).
S_i, L_i, RH_i have lambda=0 and are independent of the scalar time amplitude;
total S=sum(w_sigma*S_i), RH=sum(w_sigma^2*RH_i), rho=1/sum(sigma_i).
There is no addition of separate acPh/dis conductivities in the same band.

S-only convention tested here: A=1, b_i=1, but c_i remain active. Other modes
use explicit synthetic amplitudes. Mode selectors project predictions; this
does not implement a fitter or establish identifiability, nor reproduce the
legacy S-only adapter, which ignores c_i. Only parabolas, no Kane extension.
Legacy mapping: SPB (para_A,para_B)=(A,c1); DPB (A,B,C,D)=(A,b2,c1,c2),
meff=(m2/m1)/(N2/N1), degen=N2/N1, para_E=m1^1.5, absolute N1 explicit.
Original SeeBand modules/math_module.py has the same rho/channel functions;
its dpb_see_vs_temp_double_scatter uses signed meff and a last-T scalar weight,
so original multi-T/VBVB Seebeck must not be treated as an independent oracle.
"""

# ruff: noqa: T201 -- reproducible executable evidence.

import math
import sys
from dataclasses import dataclass

import numpy as np
import scipy
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import expit

KB, E, ME, HBAR = 1.380649e-23, 1.602176634e-19, 9.1093837139e-31, 1.054571817e-34


@dataclass(frozen=True)
class Band:
    s: int
    edge_k: float
    mass_me: float
    valleys: int
    crossover_k: float

    @property
    def dos(self):
        return self.valleys / (2 * math.pi**2) * (2 * self.mass_me * ME / HBAR**2) ** 1.5


def integral(function, eta, tail=60.0):
    # u=kBT*y^2 removes endpoint half-power singularities.
    return quad(function, 0, math.sqrt(max(eta, 0) + tail), epsabs=1e-13, epsrel=2e-11, limit=150)[
        0
    ]


def fd(order, eta):
    return integral(lambda y: 2 * y ** (2 * order + 1) * expit(eta - y * y), eta)


def population(b, mu, temperature):
    return b.dos * (KB * temperature) ** 1.5 * fd(0.5, b.s * (mu - b.edge_k) / temperature)


def potential(bands, temperature, ef):
    target = math.fsum(
        b.s * b.dos * 2 / 3 * (KB * max(b.s * (ef - b.edge_k), 0)) ** 1.5 for b in bands
    )
    scale = max(abs(target), sum(population(b, b.edge_k, temperature) for b in bands))

    def residual(mu):
        return (math.fsum(b.s * population(b, mu, temperature) for b in bands) - target) / scale

    mu = brentq(residual, -100000, 100000, xtol=1e-10, rtol=1e-14)
    assert abs(residual(mu)) < 1e-11
    return mu


def channel(b, mu, temperature, amplitude, ac=1.0, dis=1.0, direct=False):
    eta, q, mass = b.s * (mu - b.edge_k) / temperature, -b.s * E, b.mass_me * ME
    thermal = KB * temperature
    if not direct:
        f0, f1, f2 = [fd(j, eta) for j in range(3)]
        sigma = amplitude * temperature / (ac * temperature + dis * b.crossover_k) * f0
        seebeck = KB / q * (2 * f1 / f0 - eta)
        lorenz = (KB / q) ** 2 * (3 * f2 / f0 - (2 * f1 / f0) ** 2)
        hall = 3 / (2 * q * b.dos * thermal**1.5) * 0.5 * fd(-0.5, eta) / f0**2
        return sigma, seebeck, lorenz, hall
    # Calibrate tau_ref to the stated A normalization, independently of mu.
    tau_ref = amplitude / (E**2 * 2 * b.dos / (3 * mass) * (KB * 300) ** 1.5)

    def integrand(y, j):
        if y == 0:
            return 0.0
        # Integrate tau/tau_ref, so absolute quadrature tolerance is meaningful.
        rate_scale = math.sqrt(temperature / 300) * y
        rate_ac, rate_dis = rate_scale * temperature / 300, rate_scale * b.crossover_k / 300
        tau = 1 / (ac * rate_ac + dis * rate_dis)
        window = expit(eta - y * y) * expit(y * y - eta)
        if j == 3:
            return 2 * y**4 * tau * tau * window
        return 2 * y**4 * tau * window * (y * y - eta) ** j

    values = [
        integral(lambda y, j=j: integrand(y, j), eta) * tau_ref ** (2 if j == 3 else 1)
        for j in range(4)
    ]
    prefactor = 2 * b.dos / (3 * mass) * thermal**1.5
    sigma = E**2 * prefactor * values[0]
    return (
        sigma,
        KB / q * values[1] / values[0],
        (KB / q) ** 2 * (values[2] / values[0] - (values[1] / values[0]) ** 2),
        q**3 * prefactor / mass * values[3] / sigma**2,
    )


def combine(channels):
    sigma = sum(c[0] for c in channels)
    weights = [c[0] / sigma for c in channels]
    s = sum(w * c[1] for w, c in zip(weights, channels, strict=True))
    rh = sum(w * w * c[3] for w, c in zip(weights, channels, strict=True))
    lorenz = sum(w * (c[2] + (c[1] - s) ** 2) for w, c in zip(weights, channels, strict=True))
    return (
        1 / sigma,
        s,
        rh,
        lorenz,
        sum(abs(w * c[1]) for w, c in zip(weights, channels, strict=True)),
        sum(abs(w * w * c[3]) for w, c in zip(weights, channels, strict=True)),
    )


def errors(actual, expected):
    return [
        abs(actual[0] / expected[0] - 1),
        abs(actual[1] - expected[1]) / expected[4],
        abs(actual[2] - expected[2]) / expected[5],
        abs(actual[3] / expected[3] - 1),
    ]


def legacy():
    from seeband_core import math_module as mm

    ts = np.array([100.0, 300.0, 800.0])
    bands = (Band(-1, 0, 1.7, 2, 120), Band(1, 450, 0.8, 6, 550))
    mus = np.array([potential(bands, t, 100) for t in ts])
    f0 = [
        np.array([fd(0, b.s * (mu - b.edge_k) / t) for mu, t in zip(mus, ts, strict=True)])
        for b in bands
    ]
    fm = [
        np.array([fd(-0.5, b.s * (mu - b.edge_k) / t) for mu, t in zip(mus, ts, strict=True)])
        for b in bands
    ]
    ratio, a, bweight = (0.8 / 1.7) / 3, 1e5, 0.8
    rho = mm.dpb_rho_vs_temp_acPh_dis(ts, *f0, a, bweight, 120, 550, ratio)
    parts = mm.dpb_ind_elecCond_vs_temp_acPh_dis(ts, *f0, a, bweight, 120, 550, ratio)
    hall = mm.dpb_hall_vs_temp_acPh_dis(
        ts, rho, *fm, ratio, 3, a, bweight, 120, 550, 1.7**1.5, band_1_degeneracy=2
    )
    seebeck = mm.dpb_see_vs_temp_double_scatter(
        ts, ratio, 450, 100, 3, bweight, 120, 550, potentials=mus
    )
    maximum = [0.0, 0.0, 0.0]
    for j, t in enumerate(ts):
        expected = combine(
            [channel(bands[i], mus[j], t, a * (1 if i == 0 else bweight / ratio)) for i in range(2)]
        )
        assert abs(sum(part[j] for part in parts) * rho[j] - 1) < 1e-13
        values = errors((rho[j], seebeck[j], hall[j], expected[3]), expected)[:3]
        maximum = [max(x, y) for x, y in zip(maximum, values, strict=True)]
        np.testing.assert_allclose(
            mm.spb_rho_vs_temp_acPh_dis(ts[j : j + 1], f0[0][j : j + 1], a, 120),
            1 / parts[0][j : j + 1],
            rtol=1e-14,
        )
    assert max(maximum) < 3e-5
    print(
        f"Retained P18 legacy comparison PASS [rho,S,RH] errors={maximum}; "
        "shared input mu/FD integrals, no legacy root/fit validation; inherited constants differ."
    )


def main():
    print(f"SYNTHETIC acPh+dis; NumPy {np.__version__}; SciPy {scipy.__version__}")
    maxima, limit_max = [0.0] * 4, [0.0] * 4
    cases = 0
    configurations = {
        "SPB-CB": (1,),
        "SPB-VB": (-1,),
        "VBVB": (-1, -1),
        "VBCB": (-1, 1),
        "CBCB": (1, 1),
        "VBVBCB": (-1, -1, 1),
        "VBCBCB": (-1, 1, 1),
        "CBVBCB": (1, -1, 1),
    }
    for name, signs in configurations.items():
        bands = tuple(
            Band(s, (0, 450, -400)[i], (1.7, 0.8, 1.1)[i], (2, 6, 3)[i], (120, 550, 1500)[i])
            for i, s in enumerate(signs)
        )
        ef = 700 if all(s == 1 for s in signs) else -700 if all(s == -1 for s in signs) else 100
        for mode in ("S", "S+rho", "S+rho+RH"):
            amplitudes = [
                (1 if mode == "S" else 1e5)
                * b.valleys
                / bands[0].valleys
                / (b.mass_me / bands[0].mass_me)
                * (1 if mode == "S" else (1, 0.8, 1.3)[i])
                for i, b in enumerate(bands)
            ]
            for t in (100.0, 300.0, 800.0):
                mu = potential(bands, t, ef)

                def result(
                    ac=1.0, dis=1.0, direct=False, mu=mu, t=t, bands=bands, amplitudes=amplitudes
                ):
                    return combine(
                        [
                            channel(b, mu, t, a, ac, dis, direct)
                            for b, a in zip(bands, amplitudes, strict=True)
                        ]
                    )

                expected, actual = result(), result(direct=True)
                assert actual[0] > 0 and actual[3] > 0
                if len(set(signs)) == 1:
                    assert signs[0] * actual[1] < 0 and signs[0] * actual[2] < 0
                maxima = [max(a, b) for a, b in zip(maxima, errors(actual, expected), strict=True)]
                for ac, dis in ((1.0, 0.0), (0.0, 1.0)):
                    pure = result(ac, dis)
                    near = result(ac or 1e-9, dis or 1e-9, direct=True)
                    limit_max = [
                        max(a, b) for a, b in zip(limit_max, errors(near, pure), strict=True)
                    ]
                cases += 1
                if name == "VBVBCB" and mode == "S+rho+RH":
                    print(
                        f"{name} T={t:g} mu={mu:.9f}K rho={actual[0]:.9e}ohm*m "
                        f"S={actual[1]:+.9e}V/K RH={actual[2]:+.9e}m^3/C"
                    )
    # Independent rates are equal at each c_i, not at one common crossover.
    for c in (120.0, 550.0, 1500.0):
        band = Band(1, 0, 0.8, 3, c)
        mixed = channel(band, 0, c, 1e5, direct=True)
        acoustic = channel(band, 0, c, 1e5, dis=0, direct=True)
        disorder = channel(band, 0, c, 1e5, ac=0, direct=True)
        assert abs(mixed[0] / acoustic[0] - 0.5) < 1e-12
        assert abs(acoustic[0] / disorder[0] - 1) < 1e-12
        fractions = [
            channel(band, 0, t, 1e5, direct=True)[0]
            / channel(band, 0, t, 1e5, dis=0, direct=True)[0]
            for t in (100, 300, 800)
        ]
        print(f"c={c:g}K: sigma_mix/sigma_ac at T=100/300/800K={fractions}")
    assert max(maxima) < 1e-8 and max(limit_max) < 2e-8
    print(
        f"PASS {cases} temperature/configuration/mode cases: Matthiessen vs formula "
        f"[rho,S,RH,L] max errors={maxima}; pure-limit errors={limit_max}"
    )
    print(
        "Independent crossovers c=(120,550,1500)K; at T=c_i sigma_i/sigma_ac_i=0.5; "
        "rho>0; Hall/Seebeck scaled by absolute channel sums near compensation."
    )
    if "--legacy" in sys.argv:
        legacy()
    print(
        "Limits: synthetic power laws and scalar weak-field RTA; prediction projections only, "
        "not fitted parameters, API support, Kane scattering or human physics confirmation."
    )


if __name__ == "__main__":
    main()
