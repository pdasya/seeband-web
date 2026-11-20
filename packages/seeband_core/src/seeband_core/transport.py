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
from seeband_core.fermi_integrals import fermi_integral as fermi_integral


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
    reduced_mu = np.asarray(reduced_mu, dtype=float)
    integral, seebeck, lorenz, hall_numerator = _scaled_band_transport(
        temperature_k, reduced_mu, mass, scattering_lambda
    )
    scale = np.exp(np.minimum(reduced_mu, 0.0))
    if weighted_hall:
        hall = hall_numerator * scale
    else:
        with np.errstate(over="ignore", divide="ignore"):
            hall = hall_numerator / integral**2 / scale
    return integral * scale, seebeck, lorenz, hall


def _scaled_band_transport(
    temperature_k: np.ndarray,
    reduced_mu: np.ndarray,
    mass: float,
    lam: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return F and the weighted Hall moment with exp(min(η, 0)) factored out."""
    if lam < 0 or not np.isfinite(lam):
        raise ValueError("The transport exponent must be finite and nonnegative")
    eta = np.asarray(reduced_mu, dtype=float)[:, None]
    lower, upper = np.maximum(0.0, eta - 48.0), np.maximum(0.0, eta) + 48.0
    x = lower + (upper - lower) * (_NODES + 1.0) / 2.0
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
    integral = j0 / (lam + 1.0)
    seebeck = -np.sign(mass) * mm.kB / mm.e * energy_mean
    lorenz = (mm.kB / mm.e) ** 2 * variance
    jhall = np.sum(weight * x ** (2 * lam + 0.5), axis=1)
    factor = 3 * mm.hbar**3 * np.pi**2 / (mm.e * (2 * mm.kB * mm.me) ** 1.5)
    hall_numerator = -np.sign(mass) * factor * temperature_k**-1.5 / abs(mass) ** 1.5 * jhall
    return integral, seebeck, lorenz, hall_numerator / (lam + 1.0) ** 2


def ionized_transport(
    t: np.ndarray,
    p: Mapping[str, float],
    fit_mode: str,
    degen: float = 1.0,
    *,
    potentials: np.ndarray | None = None,
    band_1_degeneracy: float = 1.0,
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
            "lorenz_number": lorenz,
            "chemical_potential": mu,
        }
    r, gap = p["m_eff"] / degen, p["band_gap"]
    mu = mm.dpb_chemPot_vs_temp(t, gap, r, ef, degen) if potentials is None else potentials
    m1 = p.get("m1", 1.0)
    eta1, eta2 = -mu / t, np.sign(r) * (mu - gap) / t
    f1, s1, l1, h1 = _scaled_band_transport(t, eta1, -m1, law.energy_lambda)
    f2, s2, l2, h2 = _scaled_band_transport(
        t, eta2, r * m1 * degen ** (5.0 / 3.0), law.energy_lambda
    )
    relative_amplitude = b / abs(r)
    log_scale1, log_scale2 = np.minimum(eta1, 0.0), np.minimum(eta2, 0.0)
    with np.errstate(divide="ignore"):
        log_amplitude = np.log(abs(relative_amplitude))
    log_ratio = (log_scale2 - log_scale1) + log_amplitude
    log_scale = np.where(log_ratio > 0.0, log_scale2 + log_amplitude, log_scale1)
    scale1 = np.exp(-np.maximum(log_ratio, 0.0))
    scale2 = np.sign(relative_amplitude) * np.exp(np.minimum(log_ratio, 0.0))
    f1, f2 = f1 * scale1, f2 * scale2
    total_f = f1 + f2
    # The common Boltzmann factor cancels in the band weights. A zero
    # normalization still leaves these weights undefined.
    normalizer = np.where(np.isfinite(a) & (a != 0.0), total_f, np.nan)
    w1, w2 = f1 / normalizer, f2 / normalizer
    # Open-circuit thermal conductivity includes the parallel-channel bipolar term.
    lorenz = w1 * l1 + w2 * l2 + w1 * w2 * (s1 - s2) ** 2
    # Apply the common factor after forming the observable's coefficient.
    # Two half factors retain precision when the full exponential is subnormal.
    half_scale = np.exp(log_scale / 2.0)
    sigma_factor = a * temperature_factor
    sigma1 = (sigma_factor * f1 * half_scale) * half_scale
    sigma2 = (sigma_factor * f2 * half_scale) * half_scale
    sigma = (sigma_factor * total_f * half_scale) * half_scale
    thermal = (sigma_factor * total_f * lorenz * t * half_scale) * half_scale
    if a == 0.0:
        thermal = np.zeros_like(thermal)
    hall = (h1 * scale1 / total_f + (h2 * scale2 / total_f) * relative_amplitude) / total_f
    hall /= band_1_degeneracy
    # An exactly compensated Hall response remains zero as carrier density drops.
    with np.errstate(over="ignore", divide="ignore"):
        np.divide(hall, half_scale, out=hall, where=hall != 0.0)
        np.divide(hall, half_scale, out=hall, where=hall != 0.0)
        resistivity = 1.0 / sigma
    return {
        "seebeck": w1 * s1 + w2 * s2,
        "resistivity": resistivity,
        "hall": hall,
        "electrical_conductivity": sigma,
        "thermal_conductivity": thermal,
        "lorenz_number": lorenz,
        "chemical_potential": mu,
        "seebeck_band_1": w1 * s1,
        "seebeck_band_2": w2 * s2,
        "electrical_conductivity_band_1": sigma1,
        "electrical_conductivity_band_2": sigma2,
        # Each band's own L, which `thermal` weighs by its σ.
        "lorenz_band_1": l1,
        "lorenz_band_2": l2,
    }
