"""Explicit parabolic bands at fixed signed carrier excess D=n-p in m^-3.

Curvature signs, positive single-valley masses and carrier charges are separate.
The constants match the published transport kernels, including their inherited
k_B (density differs by about 5.2e-7 from current-SI reference quadrature).
Only the explicit parameterization uses this module; legacy predictions stay intact.
"""

import contextvars
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from math import exp, isfinite, lgamma, log, pi, sqrt

import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp

from seeband_core import math_module as mm
from seeband_core.fermi_integrals import scaled_fermi_integral
from seeband_core.model_interface import BandDiagramResult, CurveKind, ExplicitBands
from seeband_core.transport import SCATTERING_LAWS, band_transport

_SIGNS = {"vb_vb": (-1, -1), "vb_cb": (-1, 1), "cb_cb": (1, 1)}
_LOG_TINY = log(np.finfo(float).tiny)
_ROOT_CACHE: contextvars.ContextVar[
    dict[tuple[object, ...], tuple[np.ndarray, np.ndarray]] | None
] = contextvars.ContextVar("explicit_density_root_cache", default=None)


@contextmanager
def reuse_explicit_potentials() -> Iterator[None]:
    """Bounded root reuse within a caller-owned fit/evaluation scope only."""
    if _ROOT_CACHE.get() is not None:
        yield
        return
    token = _ROOT_CACHE.set({})
    try:
        yield
    finally:
        _ROOT_CACHE.reset(token)


@contextmanager
def independent_explicit_potentials() -> Iterator[None]:
    """Bypass scoped root reuse for terminal audits and independent evaluations."""
    token = _ROOT_CACHE.set(None)
    try:
        yield
    finally:
        _ROOT_CACHE.reset(token)


def _bands(
    configuration: str, p: Mapping[str, float], n1: float, n2: float
) -> tuple[tuple[int, int], np.ndarray, np.ndarray, np.ndarray]:
    if configuration not in _SIGNS:
        raise ValueError("Unknown explicit band configuration")
    mass = np.array([p["m1"], p["m1"] * p["mass_ratio"]], dtype=float)
    valleys = np.array([n1, n2], dtype=float)
    edges = np.array([0.0, p["band_offset_k"]], dtype=float)
    if (
        not np.isfinite(mass).all()
        or (mass <= 0).any()
        or not np.isfinite(valleys).all()
        or (valleys <= 0).any()
        or not np.isfinite(edges).all()
    ):
        raise ValueError("Explicit bands require finite positive masses/valleys and finite offset")
    if not np.equal(valleys, np.floor(valleys)).all():
        raise ValueError("Explicit valley counts must be positive integers")
    return _SIGNS[configuration], mass, valleys, edges


def _log_prefactors(masses: np.ndarray, valleys: np.ndarray) -> np.ndarray:
    # Spin-2 DOS C_i sqrt(epsilon): energies in kelvin, density in m^-3.
    return np.log(valleys / (2 * pi**2)) + 1.5 * np.log(2 * masses * mm.me * mm.kB / mm.hbar**2)


def _log_fhalf(eta: float) -> float:
    if eta < -36:
        # Relative omitted FD correction < exp(-36)/2^1.5 < 1e-16.
        return eta + lgamma(1.5)
    # The fixed-node rule shared with transport.py, scaled by exp(-min(eta, 0)) so that it stays
    # representable. It agrees with adaptive quadrature to 3e-14 in the log for -36 <= eta <= 2000.
    return min(eta, 0.0) + log(scaled_fermi_integral(0.5, eta))


def _solve_potentials(
    settings: ExplicitBands,
    masses: np.ndarray,
    valleys: np.ndarray,
    edges: np.ndarray,
    temperatures: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    signs = np.asarray(_SIGNS[settings.band_configuration])
    doping = settings.net_electron_density_per_m3
    assert doping is not None
    if not isfinite(doping) or (np.all(signs == signs[0]) and signs[0] * doping <= 0):
        raise mm.NoFiniteChemicalPotentialError(
            None,
            "density sign is incompatible with bands",
            code="chemical_potential_explicit_density",
        )
    prefactors = _log_prefactors(masses, valleys)
    target_log = log(abs(doping)) if doping else -np.inf
    symmetric_balance = (
        settings.band_configuration == "vb_cb"
        and doping == 0
        and masses[0] == masses[1]
        and valleys[0] == valleys[1]
    )
    roots, populations = [], []
    for temperature in temperatures:

        def log_populations(mu: float, temperature: float = float(temperature)) -> np.ndarray:
            eta = signs * (mu - edges) / temperature
            return np.asarray(
                prefactors + 1.5 * log(temperature) + np.array([_log_fhalf(x) for x in eta])
            )

        def balance(mu: float) -> float:
            logs = log_populations(mu)
            # Relative SI density residual without ever subtracting underflowed zeros.
            scale = max(float(logsumexp(logs)), target_log)
            return float(
                np.dot(signs, np.exp(logs - scale)) - np.sign(doping) * exp(target_log - scale)
            )

        if symmetric_balance:
            # The midpoint gives identical reduced energies for the two mirrored bands.
            # Solving numerically can leave a roundoff imbalance in S and Hall.
            root = float(edges[1] / 2)
        else:
            width = max(1.0, temperature, abs(float(edges[1])))
            for _ in range(128):
                if balance(-width) <= 0 <= balance(width):
                    break
                width *= 2
            else:
                raise mm.ChemicalPotentialError(
                    float(temperature), "explicit density bracket failed"
                )
            root = brentq(balance, -width, width, xtol=1e-11, rtol=4 * np.finfo(float).eps)
        residual = abs(balance(root))
        logs = log_populations(root)
        if residual > 1e-12 or not isfinite(root) or float(logsumexp(logs)) < _LOG_TINY:
            raise mm.ChemicalPotentialError(
                float(temperature), "explicit density precision cannot be certified", residual
            )
        with np.errstate(over="ignore", under="ignore"):
            pop = np.exp(logs)
        if not np.isfinite(pop).all():
            raise mm.ChemicalPotentialError(
                float(temperature), "explicit density overflow", residual
            )
        roots.append(root)
        populations.append(pop)
    return np.asarray(roots), np.asarray(populations).reshape(-1, 2)


def _potentials(
    settings: ExplicitBands,
    masses: np.ndarray,
    valleys: np.ndarray,
    edges: np.ndarray,
    temperatures: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    cache = _ROOT_CACHE.get() if temperatures.size <= 10000 else None
    key = (
        settings.band_configuration,
        settings.net_electron_density_per_m3,
        *masses,
        *valleys,
        *edges,
        temperatures.tobytes(),
    )
    if cache is not None and key in cache:
        mu, populations = cache[key]
        return mu.copy(), populations.copy()
    mu, populations = _solve_potentials(settings, masses, valleys, edges, temperatures)
    if cache is not None:
        if len(cache) >= 32:
            cache.pop(next(iter(cache)))
        cache[key] = mu.copy(), populations.copy()
    return mu, populations


def zero_temperature_density(
    configuration: str,
    parameters: Mapping[str, float],
    ef_k: float,
    n1: float,
    n2: float,
    *,
    resolve_compensation: bool = False,
) -> float:
    """Signed zero-temperature excess in m^-3 with the constants of the finite-T solver."""
    signs, masses, valleys, edges = _bands(configuration, parameters, n1, n2)
    if not isfinite(ef_k):
        raise ValueError("Zero-temperature Fermi energy must be finite")
    log_prefactors = _log_prefactors(masses, valleys)
    populations = (
        np.exp(log_prefactors)
        * (2 / 3)
        * np.maximum(np.asarray(signs) * (ef_k - edges), 0.0) ** 1.5
    )
    result = float(np.dot(signs, populations))
    if not isfinite(result):
        raise ValueError("Zero-temperature density overflow")
    if resolve_compensation and configuration == "vb_cb" and populations.min() > 0:
        # At exact pocket compensation the two logarithmic DOS prefactors have
        # already rounded before subtraction. Only treat a difference at their
        # arithmetic resolution as zero; there is no absolute density floor.
        precision = np.spacing(max(1.0, float(np.abs(log_prefactors).max())))
        if abs(result) <= 4 * precision * populations.max():
            return 0.0
    return result


def density_settings(
    settings: ExplicitBands, parameters: Mapping[str, float], n1: float, n2: float
) -> ExplicitBands:
    """Resolve each EF trial to its fixed n-p target; carrier type selects its sign.

    EF is the signed T=0 chemical potential relative to band 1, including overlaps.
    At compensation D=0 either carrier selection gives the same intrinsic state.
    """
    if not settings.uses_fermi_energy:
        return settings
    density = zero_temperature_density(
        settings.band_configuration,
        parameters,
        parameters["fermi_energy"],
        n1,
        n2,
        resolve_compensation=True,
    )
    if (settings.carrier_type == "n" and density < 0) or (
        settings.carrier_type == "p" and density > 0
    ):
        raise mm.NoFiniteChemicalPotentialError(
            0.0,
            "Fermi energy gives a carrier excess opposite to carrier_type; "
            "change Fermi energy or select the matching carrier type",
            code="fermi_energy_carrier_mismatch",
        )
    if settings.band_configuration != "vb_cb" and density == 0:
        raise mm.NoFiniteChemicalPotentialError(
            0.0,
            "Same-type bands require occupied carriers; set Fermi energy below the higher "
            "valence-band edge for VB+VB or above the lower conduction-band edge for CB+CB",
            code="fermi_energy_unoccupied_bands",
        )
    return ExplicitBands(settings.band_configuration, density)


def explicit_curves(
    settings: ExplicitBands,
    fit_mode: str,
    parameters: Mapping[str, float],
    temperatures: np.ndarray,
    scattering: str | None,
    n1: float,
    n2: float,
    kind: CurveKind = "measured",
) -> dict[str, np.ndarray]:
    """Existing public curve keys, evaluated once from a shared fixed-D root grid."""
    settings = density_settings(settings, parameters, n1, n2)
    t = np.asarray(temperatures, dtype=float)
    if t.ndim != 1 or not np.isfinite(t).all() or (t <= 0).any():
        raise mm.ChemicalPotentialError(
            None, "temperatures must be finite positive one-dimensional"
        )
    signs, masses, valleys, edges = _bands(settings.band_configuration, parameters, n1, n2)
    mu, populations = _potentials(settings, masses, valleys, edges, t)
    if kind == "chemical_potential":
        return {"chemical_potential_k": mu}
    if kind == "carrier_concentration_by_band":
        return {
            f"carrier_concentration_band_{i + 1}_per_cm3": signs[i] * populations[:, i] * 1e-6
            for i in range(2)
        }
    if scattering not in SCATTERING_LAWS and scattering != "acPhDis":
        raise ValueError("Explicit bands support acPh, dis, acPhDis and ionized scattering")
    law = SCATTERING_LAWS["acPh" if scattering == "acPhDis" else scattering]
    only_s = fit_mode == "dpb_s"
    amplitude = 1.0 if only_s else parameters.get("F" if scattering == "dis" else "A", 1.0)
    relative = (
        1.0
        if only_s and scattering != "ionized"
        else parameters.get("G" if scattering == "dis" else "B", 1.0)
    )
    if not isfinite(amplitude) or amplitude <= 0 or not isfinite(relative) or relative < 0:
        raise ValueError("Conductivity amplitude must be positive and relative weight nonnegative")
    weights = np.array([1.0, n2 / n1 * relative / parameters["mass_ratio"]])
    # The temperature law of sigma comes from the scattering law, as in transport.py: A for
    # acoustic, A*(T/300)^3 for ionized. Legacy dis is F*T, not normalized at 300 K.
    power = law.conductivity_temperature_power
    factor = t**power if scattering == "dis" else (t / 300.0) ** power
    log_f, s_bands, l_bands, log_hall = [], [], [], []
    for i in range(2):
        eta = signs[i] * (mu - edges[i]) / t
        # Remove valley multiplicity from charge sign, include it exactly once in Hall mass.
        hall_mass = signs[i] * masses[i] * valleys[i] ** (2 / 3)
        f, seebeck, lorenz, hall_weighted = band_transport(
            t, eta, hall_mass, law.energy_lambda, weighted_hall=True
        )
        tail = eta < -36
        log_integral = np.full_like(t, -np.inf)
        np.log(f, out=log_integral, where=f > 0)
        log_integral[tail] = eta[tail] + lgamma(law.energy_lambda + 1)
        # band_transport already keeps S/L stable in empty channels. Evaluate the
        # F_lambda^2*|RH| tail analytically before its Boltzmann factor underflows.
        log_h = np.full_like(t, -np.inf)
        np.log(abs(hall_weighted), out=log_h, where=hall_weighted != 0)
        prefactor = 3 * mm.hbar**3 * pi**2 / (mm.e * (2 * mm.kB * mm.me) ** 1.5)
        log_h[tail] = (
            log(prefactor)
            - 1.5 * np.log(t[tail])
            - 1.5 * log(abs(hall_mass))
            + lgamma(2 * law.energy_lambda + 1.5)
            - 2 * log(law.energy_lambda + 1)
            + eta[tail]
        )
        log_f.append(log_integral)
        log_hall.append(log_h)
        s_bands.append(seebeck)
        l_bands.append(lorenz)
    logs = np.asarray(log_f).T
    log_weights = np.full(2, -np.inf)
    np.log(weights, out=log_weights, where=weights > 0)
    if scattering == "acPhDis" and not only_s:
        # Bandwise Matthiessen law. C/D are dimensionless acoustic/disorder
        # ratios at 300 K; the two mechanisms share the same energy exponent.
        ratios = np.array([parameters.get("C", 0.0), parameters.get("D", 0.0)])
        if not np.isfinite(ratios).all() or (ratios < 0).any():
            raise ValueError("Mixed scattering ratios must be finite and nonnegative")
        log_weights = log_weights + np.log(t[:, None] / (t[:, None] + 300.0 * ratios))
    log_channels = logs + log_weights
    log_total = logsumexp(log_channels, axis=1)
    channel_fraction = np.exp(log_channels - log_total[:, None])
    sb, lb = np.asarray(s_bands).T, np.asarray(l_bands).T
    seebeck_parts = channel_fraction * sb
    total_l = (
        np.sum(channel_fraction * lb, axis=1)
        + np.prod(channel_fraction, axis=1) * (sb[:, 0] - sb[:, 1]) ** 2
    )
    if kind == "seebeck" or (kind == "measured" and only_s):
        return {"seebeck_v_per_k": np.sum(seebeck_parts, axis=1)}
    if kind == "seebeck_by_band":
        return {f"seebeck_band_{i + 1}_v_per_k": seebeck_parts[:, i] for i in range(2)}
    if kind == "lorenz_number":
        return {
            "lorenz_number_w_ohm_per_k2": total_l,
            **{f"lorenz_number_band_{i + 1}_w_ohm_per_k2": lb[:, i] for i in range(2)},
        }
    needs_hall = kind == "measured" and fit_mode == "dpb_s_rho_rh"
    with np.errstate(over="ignore", under="ignore"):
        sigma = np.exp(log(amplitude) + np.log(factor) + log_total)
        hall_terms = (
            np.exp(np.asarray(log_hall).T + 2 * log_weights - 2 * log_total[:, None])
            if needs_hall
            else np.zeros((len(t), 2))
        )
    if (sigma <= 0).any() or not np.isfinite(sigma).all() or not np.isfinite(hall_terms).all():
        raise mm.ChemicalPotentialError(None, "explicit transport scale is not representable")
    if kind == "measured":
        with np.errstate(over="ignore"):
            rho = 1 / sigma
        if not np.isfinite(rho).all():
            raise mm.ChemicalPotentialError(None, "explicit resistivity is not representable")
        output = {"seebeck_v_per_k": np.sum(seebeck_parts, axis=1), "resistivity_ohm_m": rho}
        if needs_hall:
            output["hall_m3_per_c"] = hall_terms @ -np.asarray(signs)
        return output
    if kind == "electrical_conductivity":
        return {"electrical_conductivity_s_per_m": sigma}
    if kind == "electrical_conductivity_by_band":
        return {
            f"electrical_conductivity_band_{i + 1}_s_per_m": sigma * channel_fraction[:, i]
            for i in range(2)
        }
    if kind == "thermal_conductivity":
        with np.errstate(over="ignore"):
            kappa = sigma * (t * total_l)
        if not np.isfinite(kappa).all():
            raise mm.ChemicalPotentialError(
                None, "explicit thermal conductivity is not representable"
            )
        return {"thermal_conductivity_w_per_m_k": kappa}
    raise ValueError(f"Unknown explicit DPB curve: {kind}")


def explicit_diagram(
    settings: ExplicitBands, parameters: Mapping[str, float], n1: float, n2: float
) -> BandDiagramResult:
    """Physical k in inverse angstroms, single-valley masses and T=0 root/interval."""
    supplied_ef = parameters["fermi_energy"] if settings.uses_fermi_energy else None
    signs, masses, _, edges = _bands(settings.band_configuration, parameters, n1, n2)
    doping = settings.net_electron_density_per_m3
    if supplied_ef is not None:
        if not isfinite(supplied_ef):
            raise ValueError("Zero-temperature Fermi energy must be finite")
        ef = supplied_ef
    elif settings.band_configuration == "vb_cb" and doping == 0 and edges[1] >= 0:
        if edges[1] > 0:
            ef = None
        else:
            ef = 0.0
    else:
        assert doping is not None
        width = max(1.0, abs(float(edges[1])))

        def balance(value: float) -> float:
            return (
                zero_temperature_density(settings.band_configuration, parameters, value, n1, n2)
                - doping
            )

        for _ in range(128):
            if balance(-width) <= 0 <= balance(width):
                break
            width *= 2
        else:
            raise mm.ChemicalPotentialError(0.0, "zero-temperature explicit density bracket failed")
        ef = brentq(balance, -width, width, xtol=1e-11, rtol=4 * np.finfo(float).eps)
    energy_scale_k = max(300.0, abs(float(edges[1])), abs(ef) if ef is not None else 0.0)
    extent = sqrt(2 * float(max(masses)) * mm.me * mm.kB * energy_scale_k) / mm.hbar / 1e10
    k = extent * np.linspace(-1.0, 1.0, 101)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        curves = {
            f"band_{i + 1}_energy_k": edges[i]
            + signs[i] * mm.hbar**2 * (k * 1e10) ** 2 / (2 * masses[i] * mm.me * mm.kB)
            for i in range(2)
        }
    if not np.isfinite(k).all() or any(not np.isfinite(v).all() for v in curves.values()):
        raise ValueError("Band diagram geometry is outside the finite numerical range")
    if ef is None:
        curves["fermi_energy_lower_k"] = np.full_like(k, 0.0)
        curves["fermi_energy_upper_k"] = np.full_like(k, edges[1])
    if ef is not None:
        curves["fermi_energy_k"] = np.full_like(k, ef)
    return BandDiagramResult(k * 10.0, curves)
