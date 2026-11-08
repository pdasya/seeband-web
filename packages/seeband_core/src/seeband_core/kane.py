"""Numerical Kane transport, used by band_models.SkbModel.

Lin & Liu, Sci. Rep. 12, 7056 (2022), doi:10.1038/s41598-022-09734-4.
Parameters follow SPB: signed band_mass, signed zero-temperature fermi_energy
in kelvin, and acoustic conductivity scale A. Only kane_gap_ev is new.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from numbers import Real

import numpy as np
import numpy.typing as npt
from scipy.constants import Boltzmann as KB
from scipy.constants import electron_mass as ME
from scipy.constants import elementary_charge as E
from scipy.constants import hbar as HBAR
from scipy.optimize import brentq, least_squares
from scipy.special import roots_legendre

from seeband_core.fit_module import FitProgress

FloatArray = npt.NDArray[np.float64]
Q = KB / E
FITTED = ("band_mass", "fermi_energy", "A")
MEASURED = ("seebeck_v_per_k", "resistivity_ohm_m", "hall_m3_per_c")
_NODES, _WEIGHTS = roots_legendre(64)
_NODES.setflags(write=False)
_WEIGHTS.setflags(write=False)


@dataclass(frozen=True)
class TransportIntegrals:
    # a is scaled by exp(-min(eta, 0)); ratios use the same scaling.
    a: float
    log_g: float
    log_a_over_g: float
    mean_offset: float
    variance: float
    hall_factor: float


@lru_cache(maxsize=4096)
def transport_integrals(eta: float, alpha: float) -> TransportIntegrals:
    """Acoustic SKB moments, with centred energies to avoid cancellation.

    A sqrt(x) change of variables removes the Hall integral's endpoint cusp.
    The thermal window extends 60 kBT on either side of eta (at least to x=80).
    The supported eta interval is explicit: there is no clipping of a root.
    """
    if not math.isfinite(eta) or not -80 <= eta <= 10000:
        raise ValueError("Reduced Fermi level is outside [-80, 10000]")
    if not math.isfinite(alpha) or not 0 <= alpha <= 100:
        raise ValueError("Kane nonparabolicity must be within [0, 100]")
    lower = math.sqrt(max(0.0, eta - 60))
    upper = math.sqrt(max(80.0, eta + 60))
    # Splitting the Fermi peak keeps accuracy at high degeneracy without
    # increasing the number of points over the entire integration interval.
    edges = sorted(
        {
            lower,
            upper,
            *(math.sqrt(z) for z in (eta - 16, eta, eta + 16) if lower**2 < z < upper**2),
        }
    )
    lo = np.array(edges[:-1])[:, None]
    width = np.diff(edges)[:, None]
    t = (lo + (_NODES + 1) * width / 2).ravel()
    quadrature = (_WEIGHTS * width).ravel()
    x = t * t
    offset = x - eta
    exponential = np.exp(-np.abs(offset))
    scale_log = min(eta, 0.0)
    weight = quadrature * t * np.exp(-np.abs(offset) - scale_log) / (1 + exponential) ** 2
    u = x + alpha * x * x
    v = (1 + 2 * alpha * x) ** 2 + 2
    transport = weight * u / v
    a = float(np.sum(transport))
    g = float(np.sum(weight * u**1.5))
    d = float(np.sum(weight * np.sqrt(u) / v**2))
    mean = float(np.sum(transport * offset)) / a
    variance = float(np.sum(transport * (offset - mean) ** 2)) / a
    if not all(math.isfinite(z) and z > 0 for z in (a, g, d, variance)):
        raise ArithmeticError("Invalid Kane transport integrals")
    return TransportIntegrals(
        a, math.log(g) + scale_log, math.log(a / g), mean, variance, d * g / a**2
    )


def kane_dispersion(
    wavevector_per_m: FloatArray, mass_valley_me: float, gap_ev: float
) -> FloatArray:
    """Return E(k) in eV from the band edge, including either sign of k.

    Rationalising the square root keeps the band-edge curvature accurate.
    This is a spherical valley: m_valley = mDOS / Nv**(2/3).
    """
    k = np.asarray(wavevector_per_m, dtype=np.float64)
    if not np.all(np.isfinite(k)):
        raise ValueError("Wavevectors must be finite")
    if not all(math.isfinite(z) and z > 0 for z in (mass_valley_me, gap_ev)):
        raise ValueError("Band mass and gap must be positive")
    parabolic_ev = HBAR**2 * k**2 / (2 * mass_valley_me * ME * E)
    return np.asarray(2 * parabolic_ev / (1 + np.sqrt(1 + 4 * parabolic_ev / gap_ev)))


def check_parameters(p: Mapping[str, float], degeneracy: float) -> None:
    if set(p) != {*FITTED, "kane_gap_ev"}:
        raise ValueError("Missing or unknown Kane parameters")
    if any(
        isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) for v in p.values()
    ):
        raise ValueError("Kane parameters must be finite real numbers")
    if p["band_mass"] == 0 or p["band_mass"] * p["fermi_energy"] <= 0:
        raise ValueError("band_mass and fermi_energy must describe a populated carrier band")
    if p["A"] <= 0 or p["kane_gap_ev"] <= 0:
        raise ValueError("A and kane_gap_ev must be positive")
    if not math.isfinite(degeneracy) or degeneracy <= 0:
        raise ValueError("Band degeneracy must be finite and positive")


def zero_temperature_density(band_mass: float, fermi_energy: float, gap_ev: float) -> float:
    """Total carrier density in m^-3, with the framework's signed mass/E_F convention.

    band_mass is the total DOS mass in m_e, so valley degeneracy is already
    included in its magnitude. The supplied N1 separates out a valley mass.
    """
    energy_j = KB * abs(fermi_energy)
    if band_mass * fermi_energy <= 0 or gap_ev <= 0:
        raise ValueError("The zero-temperature Fermi energy must be inside the band")
    return float(
        (2 * abs(band_mass) * ME * energy_j * (1 + energy_j / (gap_ev * E))) ** 1.5
        / (3 * math.pi**2 * HBAR**3)
    )


def fermi_state(temperature: float, p: Mapping[str, float]) -> tuple[float, TransportIntegrals]:
    alpha = Q * temperature / p["kane_gap_ev"]
    # The mass cancels between n(T,eta) and n(0,E_F), as in SPB.
    ef = abs(p["fermi_energy"])
    target = 1.5 * (math.log(ef / temperature) + math.log1p(Q * ef / p["kane_gap_ev"]))

    def residual(eta: float) -> float:
        return transport_integrals(eta, alpha).log_g - target

    eta = float(brentq(residual, -80, 10000, xtol=2e-10, maxiter=100))
    return eta, transport_integrals(eta, alpha)


def series(
    temperature: FloatArray, p: Mapping[str, float], degeneracy: float
) -> dict[str, FloatArray]:
    check_parameters(p, degeneracy)
    if temperature.ndim != 1 or not np.all(np.isfinite(temperature)) or np.any(temperature <= 0):
        raise ValueError("Temperatures must be a finite positive one-dimensional array")
    density = zero_temperature_density(p["band_mass"], p["fermi_energy"], p["kane_gap_ev"])
    states = [fermi_state(float(t), p) for t in temperature]
    eta = np.array([s[0] for s in states])
    mean = np.array([s[1].mean_offset for s in states])
    hall_factor = np.array([s[1].hall_factor for s in states])
    lorenz = Q**2 * np.array([s[1].variance for s in states])
    # a -> F0/3 in the parabolic limit, hence sigma -> A*F0, exactly
    # the acoustic scale used by the existing SPB implementation.
    sigma = 3 * p["A"] * np.exp(np.array([s[1].log_a_over_g + s[1].log_g for s in states]))
    mobility = sigma / (E * density)
    mass_sign = math.copysign(1, p["band_mass"])
    columns = {
        "seebeck_v_per_k": -mass_sign * Q * mean,
        "resistivity_ohm_m": 1 / sigma,
        "hall_m3_per_c": -mass_sign * hall_factor / (E * density),
        "chemical_potential_k": mass_sign * eta * temperature,
        "reduced_fermi_level": eta,
        "lorenz_w_ohm_per_k2": lorenz,
        "carrier_concentration_band_1_per_cm3": np.full_like(temperature, density * 1e-6),
        "mobility_m2_per_v_s": mobility,
        "hall_mobility_m2_per_v_s": mobility * hall_factor,
        "hall_factor": hall_factor,
        "electrical_conductivity_s_per_m": sigma,
        "band_edge_dos_mass_me": np.full_like(temperature, abs(p["band_mass"])),
        "band_edge_valley_mass_me": np.full_like(
            temperature, abs(p["band_mass"]) / degeneracy ** (2 / 3)
        ),
    }
    if not all(np.all(np.isfinite(v)) for v in columns.values()):
        raise ArithmeticError("Kane calculation overflowed")
    return columns


def calculate(
    min_temperature_k: float,
    max_temperature_k: float,
    points: int,
    parameters: Mapping[str, float],
    degeneracy: float,
    columns: Sequence[str],
) -> tuple[FloatArray, ...]:
    check_parameters(parameters, degeneracy)
    if not (
        math.isfinite(min_temperature_k)
        and math.isfinite(max_temperature_k)
        and 0 < min_temperature_k < max_temperature_k
    ):
        raise ValueError("Invalid temperature range")
    if isinstance(points, bool) or not isinstance(points, int) or points < 2:
        raise ValueError("At least two curve points are required")
    if "wavevector_per_m" in columns:
        p = parameters
        mass = abs(p["band_mass"]) / degeneracy ** (2 / 3)
        energy_ev = max(0.3, p["kane_gap_ev"])
        maximum_k = (
            math.sqrt(2 * mass * ME * E * energy_ev * (1 + energy_ev / p["kane_gap_ev"])) / HBAR
        )
        k = np.linspace(-maximum_k, maximum_k, points)
        energy = math.copysign(1, p["band_mass"]) * kane_dispersion(k, mass, p["kane_gap_ev"])
        return np.array([], dtype=np.float64), k, energy
    t = np.linspace(min_temperature_k, max_temperature_k, points)
    values = series(t, parameters, degeneracy)
    return (t, *(values[name] for name in columns))


def check_measurements(data: Sequence[FloatArray], band_mass: float) -> None:
    for values in data[1::2]:
        if values.size < 3:
            raise ValueError("Each Kane series needs at least three points")
    if np.any(data[3] <= 0):
        raise ValueError("Resistivity must be positive")
    if np.any(data[5] * band_mass >= 0):
        raise ValueError("Hall sign must match the selected band_mass")
    if np.any(data[1] * band_mass > 0):
        raise ValueError("Seebeck sign must match the selected band_mass")


def fit_series(
    data: Sequence[FloatArray],
    start: Sequence[float],
    bounds: Sequence[Sequence[float]],
    gap_ev: float,
    degeneracy: float,
    progress: FitProgress | None = None,
) -> FloatArray:
    """Joint solve using the common FitProgress, parameter order and covariance contract."""
    initial = np.array(start, dtype=float)
    lower, upper = np.array(bounds, dtype=float)
    if not np.all(np.isfinite([lower, upper])) or np.any(lower >= upper):
        raise ValueError("Fit bounds must be finite and ordered")
    if np.any(initial < lower) or np.any(initial > upper):
        raise ValueError("Start values are outside fit bounds")
    sign = math.copysign(1, initial[0])
    signs = np.array([sign, sign, 1.0])
    # Keep the chosen carrier branch; bounds remain in signed physical units.
    transformed = np.array([lower * signs, upper * signs])
    low = np.maximum(np.min(transformed, axis=0), 1e-12)
    high = np.max(transformed, axis=0)
    if np.any(high <= low) or np.any(initial * signs < low):
        raise ValueError("Fit bounds do not contain the selected carrier branch")
    temperatures, inverse = np.unique(np.concatenate(data[::2]), return_inverse=True)
    indices = np.split(inverse, np.cumsum([v.size for v in data[::2]])[:-1])
    s_scale = max(float(np.sqrt(np.mean(data[1] ** 2))), 1e-6)

    def residual(log_parameters: FloatArray) -> FloatArray:
        physical = np.exp(log_parameters) * signs
        p = dict(zip(FITTED, physical, strict=True)) | {"kane_gap_ev": gap_ev}
        values = series(temperatures, p, degeneracy)
        parts = []
        for j, (column, index) in enumerate(zip(MEASURED, indices, strict=True)):
            observed = data[2 * j + 1]
            predicted = values[column][index]
            error = (
                (predicted - observed) / s_scale
                if j == 0
                else np.log(np.abs(predicted)) - np.log(np.abs(observed))
            )
            parts.append(error / math.sqrt(observed.size))
        return np.concatenate(parts)

    result = least_squares(
        residual,
        np.log(initial * signs),
        bounds=(np.log(low), np.log(high)),
        max_nfev=300,
        ftol=1e-10,
        xtol=1e-10,
        gtol=1e-10,
    )
    fitted = np.asarray(np.exp(result.x) * signs)
    _, singular, vectors = np.linalg.svd(result.jac, full_matrices=False)
    covariance = np.full((3, 3), np.nan)
    if singular[-1] > singular[0] * 1e-8 and result.fun.size > 3:
        cov_log = (vectors.T / singular**2) @ vectors
        variance = float(result.fun @ result.fun) / (result.fun.size - 3)
        covariance = cov_log * variance * np.outer(fitted, fitted)
    if progress is not None:
        progress.stage_fits["joint"] = fitted, covariance
        progress.reached_iteration_limit = not result.success
    return fitted
