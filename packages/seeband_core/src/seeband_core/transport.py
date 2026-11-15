"""Unscreened power-law transport, with immutable, explicit scattering exponents.

lambda = r_tau + 1/2. Ionized impurities have r_tau=3/2 and lambda=2.
A is a free conductivity normalization in S/m: sigma=A*(T/300 K)^3*F_2.
In DPB, B is a free relative normalization (including microscopic mass factors),
and sigma_2/sigma_1=(B/abs(R/N))*F_2(eta_2)/F_2(eta_1).
No screening correction or fitted energy exponent is included.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from scipy.special import expit, roots_legendre

from seeband_core import math_module as mm


@dataclass(frozen=True)
class ScatteringLaw:
    energy_lambda: float
    tau_temperature_power: float

    @property
    def conductivity_temperature_power(self) -> float:
        return self.energy_lambda + 1.0 + self.tau_temperature_power


SCATTERING_LAWS: Mapping[str | None, ScatteringLaw] = MappingProxyType(
    {
        None: ScatteringLaw(0.0, -1.0),
        "acPh": ScatteringLaw(0.0, -1.0),
        "dis": ScatteringLaw(0.0, 0.0),
        "ionized": ScatteringLaw(2.0, 0.0),
    }
)
SCATTERING_LAMBDA: Mapping[str | None, float] = MappingProxyType(
    {name: law.energy_lambda for name, law in SCATTERING_LAWS.items()}
)
# Integrate the derivative Fermi window, resolving it even at eta >> 1. The
# omitted tails are exponentially small (exp(-48)); fixed nodes keep fit
# derivatives smooth. The stored arrays are immutable quadrature constants.
_NODES, _WEIGHTS = roots_legendre(320)
_NODES.setflags(write=False)
_WEIGHTS.setflags(write=False)


def fermi_integral(order: float, reduced_mu: float) -> float:
    """Unnormalized F_order without exponentiating a positive chemical potential."""
    if order <= -1:
        raise ValueError("Fermi integral order must exceed -1")
    eta = reduced_mu
    lower, upper = max(0.0, eta - 48.0), max(0.0, eta) + 48.0
    x = lower + (upper - lower) * (_NODES + 1.0) / 2.0
    window = expit(x - eta) * expit(eta - x)
    return float(np.sum(_WEIGHTS * (upper - lower) / 2.0 * x ** (order + 1) * window) / (order + 1))


def band_transport(
    temperature_k: np.ndarray,
    reduced_mu: np.ndarray,
    mass: float,
    scattering_lambda: float,
    *,
    weighted_hall: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return unit-amplitude F_lambda, S, L and single-band R_H (SI).

    The first output excludes the temperature law and mass normalization.
    With weighted_hall=True the last output is F_lambda**2 * R_H, evaluated
    before division by the Boltzmann factor for stable empty-band composition.
    Hall mass includes the reference valley multiplicity through |mass|^1.5.
    Integrating x^(lambda+1)(-df/dx) gives (lambda+1) F_lambda;
    the Hall moment instead uses x^(2 lambda+1/2), hence F_(2 lambda-1/2).
    """
    lam = scattering_lambda
    if lam < 0 or not np.isfinite(lam):
        raise ValueError("The transport exponent must be finite and nonnegative")
    eta = np.asarray(reduced_mu, dtype=float)[:, None]
    lower, upper = np.maximum(0.0, eta - 48.0), np.maximum(0.0, eta) + 48.0
    x = lower + (upper - lower) * (_NODES + 1.0) / 2.0
    # Scale out the Boltzmann exponential to retain ratios at large negative eta.
    scale = np.exp(np.minimum(eta, 0.0))
    # For positive eta, expit products avoid overflow; for negative eta this
    # equivalent expression divides out exp(eta) before underflow can occur.
    window = np.where(eta <= 0.0, np.exp(-x) * expit(x - eta) ** 2, expit(x - eta) * expit(eta - x))
    weight = _WEIGHTS * (upper - lower) / 2.0 * window
    longitudinal = weight * x ** (lam + 1.0)
    j0 = np.sum(longitudinal, axis=1)
    # Center at mu in the degenerate regime, at the edge otherwise. This
    # avoids subtracting enormous nearly equal moments in S and L.
    centered = x - np.maximum(eta, 0.0)
    mean = np.sum(longitudinal * centered, axis=1) / j0
    variance = np.sum(longitudinal * (centered - mean[:, None]) ** 2, axis=1) / j0
    energy_mean = mean - np.minimum(eta[:, 0], 0.0)
    integral = j0 * scale[:, 0] / (lam + 1.0)
    seebeck = -np.sign(mass) * mm.kB / mm.e * energy_mean
    lorenz = (mm.kB / mm.e) ** 2 * variance
    jhall = np.sum(weight * x ** (2 * lam + 0.5), axis=1)
    factor = 3 * mm.hbar**3 * np.pi**2 / (mm.e * (2 * mm.kB * mm.me) ** 1.5)
    hall_numerator = -np.sign(mass) * factor * temperature_k**-1.5 / abs(mass) ** 1.5 * jhall
    if weighted_hall:
        hall = hall_numerator * scale[:, 0] / (lam + 1.0) ** 2
    else:
        with np.errstate(over="ignore", divide="ignore"):
            hall = hall_numerator / j0**2 / scale[:, 0]
    return integral, seebeck, lorenz, hall


def ionized_transport(
    t: np.ndarray,
    p: Mapping[str, float],
    fit_mode: str,
    degen: float = 1.0,
    *,
    potentials: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Shared predictions for fitting, measured grids and displayed curves."""
    t = np.asarray(t, dtype=float)
    a, b = p.get("A", 1.0), p.get("B", 1.0)
    law = SCATTERING_LAWS["ionized"]
    temperature_factor = (t / 300.0) ** law.conductivity_temperature_power
    ef = p["fermi_energy"]
    if fit_mode.startswith("spb"):
        mass = p["band_mass"]
        mu = mm.spb_chemPot_vs_temp(t, mass, ef) if potentials is None else potentials
        f, s, lorenz, h = band_transport(t, np.sign(mass) * mu / t, mass, law.energy_lambda)
        sigma = a * temperature_factor * f
        return {
            "seebeck": s,
            "resistivity": 1.0 / sigma,
            "hall": h,
            "electrical_conductivity": sigma,
            "thermal_conductivity": lorenz * sigma * t,
            "chemical_potential": mu,
        }
    r, gap = p["m_eff"] / degen, p["band_gap"]
    mu = mm.dpb_chemPot_vs_temp(t, gap, r, ef, degen) if potentials is None else potentials
    m1 = p.get("m1", 1.0)
    f1, s1, l1, h1 = band_transport(t, -mu / t, -m1, law.energy_lambda, weighted_hall=True)
    f2, s2, l2, h2 = band_transport(
        t,
        np.sign(r) * (mu - gap) / t,
        r * m1 * degen ** (5.0 / 3.0),
        law.energy_lambda,
        weighted_hall=True,
    )
    sigma1, sigma2 = a * temperature_factor * f1, a * temperature_factor * b / abs(r) * f2
    sigma = sigma1 + sigma2
    hall_base = f1 + b / abs(r) * f2
    w1, w2 = sigma1 / sigma, sigma2 / sigma
    # Open-circuit thermal conductivity includes the parallel-channel bipolar term.
    thermal = t * (l1 * sigma1 + l2 * sigma2 + sigma1 * w2 * (s1 - s2) ** 2)
    return {
        "seebeck": w1 * s1 + w2 * s2,
        "resistivity": 1.0 / sigma,
        "hall": (h1 / hall_base + (h2 / hall_base * b / abs(r)) * b / abs(r)) / hall_base,
        "electrical_conductivity": sigma,
        "thermal_conductivity": thermal,
        "chemical_potential": mu,
        "seebeck_band_1": w1 * s1,
        "seebeck_band_2": w2 * s2,
        "electrical_conductivity_band_1": sigma1,
        "electrical_conductivity_band_2": sigma2,
    }
