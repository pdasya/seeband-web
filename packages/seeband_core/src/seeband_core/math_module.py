import contextlib
import contextvars
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from importlib import resources
from typing import Any

import numpy as np
from scipy.optimize import brentq
from scipy.special import expit

from seeband_core.fermi_integrals import fermi_integral, scaled_fermi_integral
from seeband_core.model_scales import BOLTZMANN_EV_PER_K

"""
#################################################
Constants
#################################################
"""

kB = 1.38064852e-23
e = 1.602176634e-19
h = 6.62607015e-34
hbar = h / (2 * np.pi)
me = 9.1093837e-31
# Historical kernels below retain lambda=0; generic exponents live in transport.py.


def _load_fermi_table() -> np.ndarray:
    table: list[list[float]] = []
    with (resources.files("seeband_core") / "data" / "fermi_int_-10_20.txt").open("r") as file:
        for line in file.readlines():
            columns = line.split("\t")
            table.append([float(columns[0]), float(columns[1])])
    return np.array(table)


fermi1_10 = _load_fermi_table()


"""
#################################################
Fermi integral
#################################################
"""


def fdint_robust(s: float, eta: float, T: float) -> float:
    return fermi_integral(s, eta / T)


fdint_vec: Callable[..., Any] = np.vectorize(fdint_robust)


def fdint(s: Any, eta: Any, T: Any) -> Any:
    """`fdint_vec`, with scalars passed straight to `fdint_robust`.

    `np.vectorize` costs more than the integral for one value, and most calls here are for one.
    The value is the same to the last bit; it comes back as a numpy float, so that a division by
    0 or an overflow after it still gives inf with a warning, as from `fdint_vec`, rather than
    raising.
    """
    if np.ndim(s) == 0 and np.ndim(eta) == 0 and np.ndim(T) == 0:
        return np.float64(fdint_robust(s, eta, T))
    return fdint_vec(s, eta, T)


# Calculates Fermi integrals for a single band
def spb_fermiInt_vs_temp(
    s: float,
    T: np.ndarray,
    mass_sign: float,
    fermi_energy: float,
    *,
    potentials: np.ndarray | None = None,
) -> np.ndarray:
    if potentials is None:
        potentials = spb_chemPot_vs_temp(T, mass_sign, fermi_energy)
    fermiInt = np.zeros(shape=len(T))

    for i, (temp, mu) in enumerate(zip(T, potentials, strict=True)):
        fermiInt[i] = fdint(s, mass_sign * mu, temp)

    return fermiInt


# Calculates Fermi integrals for two bands
def dpb_fermiInt_vs_temp(
    s: float,
    T: np.ndarray,
    mass: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    *,
    potentials: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    if potentials is None:
        potentials = dpb_chemPot_vs_temp(T, gap, mass, fermi_energy, degen)
    fermiInt_1 = np.zeros(shape=len(T))
    fermiInt_2 = np.zeros(shape=len(T))

    for i, (temp, mu) in enumerate(zip(T, potentials, strict=True)):
        fermiInt_1[i] = fdint(s, -mu, temp)
        fermiInt_2[i] = fdint(s, np.sign(mass) * (mu - gap), temp)

    return fermiInt_1, fermiInt_2


"""
#################################################
Basic thermoelectric functions
#################################################
"""


# General formula for calculating the Onsager coefficient of a single band
def onsi_general(eta: float, meff: float, K: float, beta: float, T: float) -> float:
    result: float = (
        -np.sign(meff)
        * (kB / e)
        * K
        * T ** (beta + 1)
        / abs(meff)
        * (
            2 * fdint(1, np.sign(meff) * eta, T)
            - np.sign(meff) * fdint(0, np.sign(meff) * eta, T) * eta / T
        )
    )
    return result


# General formula for calculating the electrical conductivity of a single band
def sigma_general(eta: float, meff: float, K: float, beta: float, T: float) -> float:
    # Temperature factor defined as beta + 1, since 1 is obtained from partial integration instead
    # of 3/2
    result: float = K * T ** (beta + 1) / abs(meff) * fdint(0, np.sign(meff) * eta, T)
    return result


"""
#################################################
Useful functions
#################################################
"""


# Calculates the charge carrier concentration of a single band
def spb_carCon(eta: float, meff: float, T: float) -> float:
    if T == 0:
        # If Fermi energy is inside the band ...
        if eta * np.sign(meff) > 0:
            at_zero_kelvin: float = (
                (4 * np.pi * (2 * np.abs(meff) * me * kB * np.abs(eta) / h**2) ** 1.5)
                * (2 / 3)
                * 1e-6
            )
            return at_zero_kelvin

        # If Fermi energy is outside the band ...
        else:
            return 0
    else:
        scale = 4 * np.pi * (2 * np.abs(meff) * me * kB * T / h**2) ** 1.5
        x = float(np.sign(meff) * eta / T)
        if x < -700.0:
            # Restore occupation after applying the physical density prefactor.
            half_scale = np.exp(x / 2)
            return float((scale * 1e-6 * scaled_fermi_integral(0.5, x) * half_scale) * half_scale)
        carrier_concentration: float = scale * fdint(0.5, np.sign(meff) * eta, T) * 1e-6
        return carrier_concentration


class ChemicalPotentialError(ValueError):
    """A density-conserving finite chemical potential could not be certified."""

    def __init__(
        self, temperature: float | None, reason: str, residual: float | None = None
    ) -> None:
        self.temperature = temperature
        self.reason = reason
        self.residual = residual
        self.normalized_residual = residual
        super().__init__(f"Chemical potential at {temperature} K: {reason} (residual={residual})")


class NoFiniteChemicalPotentialError(ChemicalPotentialError):
    """The parameters lie outside the analytically admissible finite-root model domain."""

    def __init__(
        self,
        temperature: float | None,
        reason: str,
        residual: float | None = None,
        *,
        code: str | None = None,
    ) -> None:
        super().__init__(temperature, reason, residual)
        self.code = code


@dataclass(frozen=True)
class ChemicalPotentialResult:
    """Checked roots in kelvin, absolute normalized residuals and per-point status."""

    chemical_potential: np.ndarray
    normalized_residual: np.ndarray
    status: np.ndarray


# Roots solved within the current `reuse_chemical_potential` scope, or None outside one.
# Only the roots and residuals are kept: a solve that is kept succeeded, so each status is
# "converged", and a string status per point would take more room than both.
_REUSED_ROOTS: contextvars.ContextVar[
    dict[tuple[bytes, ...], tuple[np.ndarray, np.ndarray]] | None
] = contextvars.ContextVar("reused_chemical_potential", default=None)
# Within a fit each set of parameters differs, so only the last few are worth keeping.
_REUSED_ROOTS_LIMIT = 32


@contextlib.contextmanager
def reuse_chemical_potential() -> Iterator[None]:
    """Solve μ(T) once for each temperature array and parameters within this scope.

    A curve of S, ρ and R_H needs the same μ(T) for each, and a solve is most of its time. The
    roots are those of a fresh solve, to the last bit, and the scope drops them as it ends, so
    nothing outlives one call. A nested scope uses the outer one's roots.
    """
    if _REUSED_ROOTS.get() is not None:
        yield
        return
    token = _REUSED_ROOTS.set({})
    try:
        yield
    finally:
        _REUSED_ROOTS.reset(token)


@contextlib.contextmanager
def independent_chemical_potential() -> Iterator[None]:
    """Temporarily bypass root reuse for an independent terminal fit audit."""
    token = _REUSED_ROOTS.set(None)
    try:
        yield
    finally:
        _REUSED_ROOTS.reset(token)


def _key_bytes(value: object) -> bytes | None:
    """The value's kind and bytes, as the solve gets it, or None if it cannot be a key.

    Bytes, not floats, so that -0.0 and 0.0 stay apart, as the solve can tell them apart. A float
    and an np.float64, its subclass, share a key: they are the same double and give the same bits
    in each operation, and the solve divides only by numpy temperatures or a checked scale, so the
    zero division where a float raises and an np.float64 warns cannot occur. Any other numpy type
    keeps its own, because the solve computes with the value as given, and an np.float32 gives
    other numbers than the float64 of the same value. Anything but a number is solved each time.
    """
    if value is None:
        return b"none:"
    if isinstance(value, float):
        return b"float:" + np.float64(value).tobytes()
    if isinstance(value, np.number):
        return value.dtype.str.encode() + b":" + value.tobytes()
    if isinstance(value, int):
        return type(value).__qualname__.encode() + b":" + str(value).encode()
    return None


def _converged(
    roots: np.ndarray, residuals: np.ndarray, shape: tuple[int, ...]
) -> ChemicalPotentialResult:
    return ChemicalPotentialResult(roots, residuals, np.full(shape, "converged"))


def _chemical_potential_diagnostics(
    temp_array: np.ndarray,
    mass: float,
    fermi_energy: float,
    gap: float | None = None,
    degen: float = 1.0,
) -> ChemicalPotentialResult:
    """The solved roots, once for each temperature array and parameters within a reuse scope.

    Only a solve that succeeds is kept, so one that fails raises again each time, as before.
    """
    reused = _REUSED_ROOTS.get()
    if reused is None:
        return _solve_chemical_potential(temp_array, mass, fermi_energy, gap, degen)
    parameters: list[bytes] = []
    for value in (mass, fermi_energy, gap, degen):
        part = _key_bytes(value)
        if part is None:
            return _solve_chemical_potential(temp_array, mass, fermi_energy, gap, degen)
        parameters.append(part)
    # The solve converts the temperatures the same way first, so these bytes are what it gets.
    temperatures = np.asarray(temp_array, dtype=float)
    key = (str(temperatures.shape).encode(), temperatures.tobytes(), *parameters)
    found = reused.get(key)
    if found is None:
        solved = _solve_chemical_potential(temp_array, mass, fermi_energy, gap, degen)
        if len(reused) >= _REUSED_ROOTS_LIMIT:
            del reused[next(iter(reused))]
        found = (solved.chemical_potential, solved.normalized_residual)
        reused[key] = found
    roots, residuals = found
    # Copies, so that a caller changing its array cannot change another's.
    return _converged(roots.copy(), residuals.copy(), temperatures.shape)


def _solve_chemical_potential(
    temp_array: np.ndarray,
    mass: float,
    fermi_energy: float,
    gap: float | None = None,
    degen: float = 1.0,
) -> ChemicalPotentialResult:
    """Solve signed density balance in mu/T, then certify the unchanged density equation.

    Each unique temperature uses an independent bracket, so caller ordering and other
    temperatures cannot select a different root. Invalid points raise immediately.
    """
    temperatures = np.asarray(temp_array, dtype=float)
    if temperatures.ndim != 1:
        raise ChemicalPotentialError(None, "temperatures must be a one-dimensional array")
    invalid = ~np.isfinite(temperatures) | (temperatures <= 0)
    if invalid.any():
        raise ChemicalPotentialError(
            float(temperatures[invalid][0]), "temperature must be finite and positive"
        )
    if not np.isfinite(mass) or not np.isfinite(fermi_energy):
        raise ChemicalPotentialError(
            None, "mass must be finite and nonzero; Fermi energy must be finite"
        )
    if gap is not None and (not np.isfinite(gap) or not np.isfinite(degen) or degen <= 0):
        raise ChemicalPotentialError(
            None, "gap must be finite and degeneracy must be finite and positive"
        )
    if mass == 0:
        raise NoFiniteChemicalPotentialError(
            None,
            "zero band mass is outside the supported model domain",
            code="chemical_potential_zero_mass",
        )
    if (gap is None and fermi_energy * np.sign(mass) <= 0) or (
        gap is not None and mass < 0 and fermi_energy >= max(0.0, gap)
    ):
        raise NoFiniteChemicalPotentialError(
            None,
            "no finite root for zero carrier density",
            code=(
                "chemical_potential_spb_fermi_energy"
                if gap is None
                else "chemical_potential_dpb_fermi_energy"
            ),
        )

    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        effective_mass = mass if gap is None else mass * np.float64(degen) ** (5 / 3)
        target = (
            spb_carCon(fermi_energy, mass, 0)
            if gap is None
            else (
                -spb_carCon(fermi_energy, -1, 0)
                + np.sign(mass) * spb_carCon(fermi_energy - gap, effective_mass, 0)
            )
        )
    if not np.isfinite(effective_mass) or effective_mass == 0 or not np.isfinite(target):
        raise ChemicalPotentialError(None, "nonfinite density parameters")

    unique, inverse = np.unique(temperatures, return_inverse=True)
    roots = np.empty_like(unique)
    residuals = np.empty_like(unique)
    intrinsic_gap = gap if mass > 0 and target == 0 else None
    center = 0.0 if intrinsic_gap is None else intrinsic_gap / 2
    if intrinsic_gap is not None and effective_mass == 1.0 and center - intrinsic_gap == -center:
        # The two density contributions are identical at the representable midpoint.
        # Using it directly also preserves exact cancellation of symmetric Hall channels.
        return _converged(
            np.full_like(temperatures, center), np.zeros_like(temperatures), temperatures.shape
        )
    for index, temp in enumerate(unique):

        def intrinsic_balance(mu: float, offset: float, temperature: float) -> float:
            assert intrinsic_gap is not None
            x1, x2 = -mu / temperature, (mu - intrinsic_gap) / temperature
            # In the doubly dilute regime the two large reduced potentials
            # differ by just twice the displacement from the center.
            log_scale_ratio = 2 * offset if x1 <= 0 and x2 <= 0 else min(x2, 0.0) - min(x1, 0.0)
            log_density_ratio = (
                1.5 * np.log(effective_mass)
                + log_scale_ratio
                + np.log(scaled_fermi_integral(0.5, x2) / scaled_fermi_integral(0.5, x1))
            )
            # (n-p)/(n+p) = tanh(log(n/p)/2), including when n and p round to zero.
            return float(np.tanh(log_density_ratio / 2))

        def balance(eta: float, temperature: float = float(temp)) -> float:
            with np.errstate(over="ignore", under="ignore", invalid="ignore"):
                mu = center + eta * temperature
                if intrinsic_gap is not None and np.isfinite(mu):
                    return intrinsic_balance(mu, eta, temperature)
                first = spb_carCon(mu, mass if gap is None else -1, temperature)
                second = 0.0 if gap is None else spb_carCon(mu - gap, effective_mass, temperature)
                density = first if gap is None else -first + np.sign(mass) * second
                scale = max(abs(first) + abs(second), abs(target))
                if not np.isfinite(scale) or scale <= 0 or not np.isfinite(mu):
                    raise ChemicalPotentialError(
                        temperature, "density scale is not finite and positive"
                    )
                if scale < np.finfo(float).tiny:
                    raise ChemicalPotentialError(
                        temperature, "subnormal density scale cannot certify relative precision"
                    )
                return float((density - target) / scale)

        width = max(1.0, abs(fermi_energy / temp), 0.0 if gap is None else abs(gap / temp))
        try:
            for _ in range(128):
                left, right = balance(-width), balance(width)
                if left == 0 or right == 0 or np.sign(left) != np.sign(right):
                    break
                width *= 2
            else:
                raise ChemicalPotentialError(float(temp), "could not bracket density balance")
            eta = brentq(
                balance,
                -width,
                width,
                xtol=np.nextafter(0.0, 1.0),
                rtol=4 * np.finfo(float).eps,
                maxiter=256,
            )
            mu = float(center + eta * temp)
            # Set when the root lies between two adjacent floats: no binary64 μ can meet the
            # tolerance, which is a limit of the representation, not a failed solve.
            unrepresentable = False
            if intrinsic_gap is None:
                residual = abs(balance(eta))
            else:
                candidates = (mu, float(np.nextafter(mu, -np.inf)), float(np.nextafter(mu, np.inf)))
                signed = [
                    intrinsic_balance(candidate, (candidate - center) / temp, temp)
                    for candidate in candidates
                ]
                residual, mu = min(
                    (abs(value), candidate)
                    for value, candidate in zip(signed, candidates, strict=True)
                )
                unrepresentable = np.sign(signed[1]) != np.sign(signed[2])
        except ChemicalPotentialError:
            raise
        except (ValueError, RuntimeError, OverflowError) as exc:
            raise ChemicalPotentialError(float(temp), "bracketed density solve failed") from exc
        if not np.isfinite(residual) or residual > 1e-12:
            raise ChemicalPotentialError(
                float(temp),
                "no representable chemical potential meets the density tolerance"
                if unrepresentable and np.isfinite(residual)
                else "density residual exceeds tolerance",
                residual,
            )
        roots[index] = mu
        residuals[index] = residual
    return _converged(roots[inverse], residuals[inverse], temperatures.shape)


def spb_chemPot_diagnostics(
    temp_array: np.ndarray, band_mass: float, fermi_energy: float
) -> ChemicalPotentialResult:
    """Return SPB roots and their density checks, or raise ChemicalPotentialError."""
    return _chemical_potential_diagnostics(temp_array, band_mass, fermi_energy)


def dpb_chemPot_diagnostics(
    temp_array: np.ndarray, gap: float, meff: float, fermi_energy: float, degen: float
) -> ChemicalPotentialResult:
    """Return DPB roots and their density checks, or raise ChemicalPotentialError."""
    return _chemical_potential_diagnostics(temp_array, meff, fermi_energy, gap, degen)


# Calculates the signed density imbalance of a single band at a temperature T
def spb_chemPot(eta_here: np.ndarray, temp: float, band_mass: float, fermi_energy: float) -> float:
    """Signed SPB density residual; compatibility helper for external callers."""
    result = spb_carCon(eta_here[0], band_mass, temp) - spb_carCon(fermi_energy, band_mass, 0)
    return float(result)


# Calculates the temperature-dependent chemical potential of a single band
def spb_chemPot_vs_temp(
    temp_array: np.ndarray, band_mass: float, fermi_energy: float
) -> np.ndarray:
    return spb_chemPot_diagnostics(temp_array, band_mass, fermi_energy).chemical_potential


# Calculates the chemical potential of two bands at a temperature T with variable degeneracy ratio
# degen
def dpb_chemPot(
    eta_here: np.ndarray, temp: float, gap: float, meff: float, fermi_energy: float, degen: float
) -> float:
    """Signed DPB density residual; compatibility helper for external callers."""
    result = (
        (-1) * spb_carCon(eta_here[0], -1, temp)
        + np.sign(meff) * spb_carCon(eta_here[0] - gap, meff * degen ** (5 / 3), temp)
        - (
            (-1) * spb_carCon(fermi_energy, -1, 0)
            + np.sign(meff) * spb_carCon(fermi_energy - gap, meff * degen ** (5 / 3), 0)
        )
    )
    return float(result)


# Calculates the temperature-dependent chemical potential of two bands
def dpb_chemPot_vs_temp(
    temp_array: np.ndarray, gap: float, meff: float, fermi_energy: float, degen: float
) -> np.ndarray:
    return dpb_chemPot_diagnostics(temp_array, gap, meff, fermi_energy, degen).chemical_potential


def _scaled_integrals(order: float, reduced: np.ndarray) -> np.ndarray:
    return np.fromiter(
        (scaled_fermi_integral(order, float(x)) for x in reduced), dtype=float, count=len(reduced)
    )


def _band_seebeck(reduced: np.ndarray, mass_sign: float) -> np.ndarray:
    mean = np.empty_like(reduced)
    # For eta >= 40 the exponentially small parts of F0 and F1 are below the
    # precision of the ratio. Cancel the leading eta analytically.
    degenerate = reduced >= 40.0
    mean[degenerate] = (np.pi**2 / 3) / reduced[degenerate]
    x = reduced[~degenerate]
    mean[~degenerate] = 2 * _scaled_integrals(1, x) / _scaled_integrals(0, x) - x
    return -mass_sign * (kB / e) * mean


def _band_lorenz(reduced: np.ndarray) -> np.ndarray:
    variance = np.empty_like(reduced)
    degenerate = reduced >= 40.0
    variance[degenerate] = np.pi**2 / 3 - (np.pi**2 / 3 / reduced[degenerate]) ** 2
    x = reduced[~degenerate]
    f0 = _scaled_integrals(0, x)
    variance[~degenerate] = (
        3 * _scaled_integrals(2, x) / f0 - (2 * _scaled_integrals(1, x) / f0) ** 2
    )
    return (kB / e) ** 2 * variance


def _dpb_reduced_potentials(
    temperatures: np.ndarray,
    mass: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    potentials: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    if potentials is None:
        potentials = dpb_chemPot_vs_temp(temperatures, gap, mass, fermi_energy, degen)
    return -potentials / temperatures, np.sign(mass) * (potentials - gap) / temperatures


def _dpb_conductivity_weights(
    reduced1: np.ndarray, reduced2: np.ndarray, conductivity_factor: float | np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    with np.errstate(divide="ignore"):
        # Use log sigma2/sigma1 before either raw conductivity underflows.
        # A zero relative amplitude describes an absent second channel. The amplitude is one
        # number at every temperature, as for acPh and dis; a mixed mechanism whose relative
        # amplitude varies with T, such as acPhDis, must pass it per temperature.
        log_ratio = (
            np.minimum(reduced2, 0.0)
            - np.minimum(reduced1, 0.0)
            + np.log(_scaled_integrals(0, reduced2) / _scaled_integrals(0, reduced1))
            + np.log(np.abs(conductivity_factor))
        )
    weight1, weight2 = expit(-log_ratio), expit(log_ratio)
    negative = np.broadcast_to(np.asarray(conductivity_factor) < 0, log_ratio.shape)
    if negative.any():
        # The low-level curve API accepts signed amplitudes. Use the signed
        # denominator, with expm1 resolving near cancellation.
        x = log_ratio[negative]
        norm = -np.expm1(-np.abs(x))
        difference = np.where(x > 0, -norm, norm)
        with np.errstate(divide="ignore", invalid="ignore"):
            weight1[negative] = np.exp(-np.maximum(x, 0)) / difference
            weight2[negative] = -np.exp(np.minimum(x, 0)) / difference
    return weight1, weight2


def _dpb_seebeck_contributions(
    reduced1: np.ndarray, reduced2: np.ndarray, mass: float, conductivity_factor: float | np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    weight1, weight2 = _dpb_conductivity_weights(reduced1, reduced2, conductivity_factor)
    return (
        weight1 * _band_seebeck(reduced1, -1),
        weight2 * _band_seebeck(reduced2, float(np.sign(mass))),
    )


def dpb_effective_lorenz(
    temperatures: np.ndarray,
    mass: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    relative_amplitude: float,
) -> np.ndarray:
    # Equal temperature factors cancel in the acoustic and disorder weights.
    x1, x2 = _dpb_reduced_potentials(temperatures, mass, gap, fermi_energy, degen)
    weight1, weight2 = _dpb_conductivity_weights(x1, x2, relative_amplitude / abs(mass))
    difference = _band_seebeck(x1, -1) - _band_seebeck(x2, float(np.sign(mass)))
    result: np.ndarray = (
        weight1 * _band_lorenz(x1) + weight2 * _band_lorenz(x2) + weight1 * weight2 * difference**2
    )
    return result


def spb_lorNum_vs_temp(temp_array: np.ndarray, fermi_energy: float, band_mass: float) -> np.ndarray:
    potentials = spb_chemPot_vs_temp(temp_array, band_mass, fermi_energy)
    return _band_lorenz(np.sign(band_mass) * potentials / temp_array)


def dpb_lorNum_vs_temp(
    temp_array: np.ndarray, meff: float, gap: float, fermi_energy: float, degen: float
) -> tuple[np.ndarray, np.ndarray]:
    x1, x2 = _dpb_reduced_potentials(temp_array, meff, gap, fermi_energy, degen)
    return _band_lorenz(x1), _band_lorenz(x2)


"""
#################################################
Functions used for calculating the thermoelectric properties
#################################################
"""

"""
SPB
"""


# Calculates the Seebeck coefficient of a single band
def spb_see_vs_temp(
    temp_array: np.ndarray,
    fermi_energy: float,
    band_mass: float,
    scal_fac: float = 1.0,
    *,
    potentials: np.ndarray | None = None,
) -> np.ndarray:
    """Calculates the Seebeck coefficient of a single bands at various temperatures for the
    only-Seebeck mode

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    fermi_energy : float
        Fitting parameter, representing the position of the Fermi energy with respect to the maximum
        of the band
    band_mass : float
        Mass of the band
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray
        Numpy array of Seebeck coefficient values
    """

    if potentials is None:
        potentials = spb_chemPot_vs_temp(temp_array, band_mass, fermi_energy)
    sign = float(np.sign(band_mass))
    return scal_fac * _band_seebeck(sign * potentials / temp_array, sign)


# Calculates the electrical resistivity of a single band for acoustic-phonon scattering
def spb_rho_vs_temp_acPh(
    temp_array: np.ndarray, sig: np.ndarray, para_A: float, scal_fac: float = 1.0
) -> np.ndarray:
    """Calculates the resistivity of a single band at various tempeatures for a given
    acoustic-phonon scattering parameter.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig : numpy.ndarray
        'Pristine' conductivity of the band, calculated with mass = mass_sign, K = 1 and beta = 0 at
        the temperatures given by temp_array
    para_A : float
        Fitting parameter, representing the prefactor of acoustic-phonon scattering
    scal_fac : float
        Scaling factor, by which the function is multiplied

    Returns
    -------
    out : numpy.ndarray
        Numpy array of resistivity values
    """

    return scal_fac / (para_A * sig)


# Calculates the electrical conductivity of a single band for acoustic-phonon scattering
def spb_elecCond_vs_temp_acPh(
    temp_array: np.ndarray, sig: np.ndarray, para_A: float, scal_fac: float = 1.0
) -> np.ndarray:
    """Calculates the electrical conductivity of a single band at various temperatures for a given
    acoustic-phonon scattering parameter.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig : numpy.ndarray
        'Pristine' conductivity of the band, calculated with mass = mass_sign, K = 1 and beta = 0 at
        the temperatures given by temp_array
    para_A : float
        Fitting parameter, representing the prefactor of acoustic-phonon scattering
    scal_fac : float
        Scaling factor, by which the function is multiplied

    Returns
    -------
    out : numpy.ndarray
        Numpy array of electrical conductivity values
    """

    return scal_fac * para_A * sig


# Calculates the electron thermal conductivity of a single band for acoustic-phonon scattering
def spb_thermCond_vs_temp_acPh(
    temp_array: np.ndarray,
    sig: np.ndarray,
    fermi_energy: float,
    band_mass: float,
    para_A: float,
    scal_fac: float = 1.0,
) -> np.ndarray:
    """Calculates the electron thermal conductivity of a single band at various temperatures for a
    given acoustic-phonon scattering parameter.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig : numpy.ndarray
        'Pristine' conductivity of the band, calculated with mass = mass_sign, K = 1 and beta = 0 at
        the temperatures given by temp_array
    para_A : float
        Fitting parameter, representing the prefactor of acoustic-phonon scattering
    scal_fac : float
        Scaling factor, by which the function is multiplied

    Returns
    -------
    out : numpy.ndarray
        Numpy array of electron thermal conductivity values
    """

    result: np.ndarray = (
        spb_elecCond_vs_temp_acPh(temp_array, sig, para_A, scal_fac)
        * spb_lorNum_vs_temp(temp_array, fermi_energy, band_mass)
        * temp_array
    )
    return result


# Calculates the electrical resistivity of a single band for alloy-disorder scattering
def spb_rho_vs_temp_dis(
    temp_array: np.ndarray, sig: np.ndarray, para_A: float, scal_fac: float = 1.0
) -> np.ndarray:
    """Calculates the resistivity of a single band at various temperatures for a given
    alloy-disorder scattering parameter.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig : numpy.ndarray
        'Pristine' conductivity of the band, calculated with mass = mass_sign, K = 1 and beta = 0 at
        the temperatures given by temp_array
    para_A : float
        Fitting parameter, representing the prefactor of alloy-disorder scattering
    scal_fac : float
        Scaling factor, by which the function is multiplied

    Returns
    -------
    out : numpy.ndarray
        Numpy array of resistivity values
    """

    result: np.ndarray = scal_fac / (para_A * temp_array * sig)
    return result


# Calculates the electrical conductivity of a single band for alloy-disorder scattering
def spb_elecCond_vs_temp_dis(
    temp_array: np.ndarray, sig: np.ndarray, para_A: float, scal_fac: float = 1.0
) -> np.ndarray:
    """Calculates the electrical conductivity of a single band at various temperatures for a given
    alloy-disorder scattering parameter.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig : numpy.ndarray
        'Pristine' conductivity of the band, calculated with mass = mass_sign, K = 1 and beta = 0 at
        the temperatures given by temp_array
    para_A : float
        Fitting parameter, representing the prefactor of alloy-disorder scattering
    scal_fac : float
        Scaling factor, by which the function is multiplied

    Returns
    -------
    out : numpy.ndarray
        Numpy array of electrical conductivity values
    """

    result: np.ndarray = scal_fac * para_A * temp_array * sig
    return result


# Calculates the electron thermal conductivity of a single band for alloy-disorder scattering
def spb_thermCond_vs_temp_dis(
    temp_array: np.ndarray,
    sig: np.ndarray,
    fermi_energy: float,
    band_mass: float,
    para_A: float,
    scal_fac: float = 1.0,
) -> np.ndarray:
    """Calculates the electron thermal conductivity of a single band at various temperatures for a
    given alloy-disorder scattering parameter.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig : numpy.ndarray
        'Pristine' conductivity of the band, calculated with mass = mass_sign, K = 1 and beta = 0 at
        the temperatures given by temp_array
    para_A : float
        Fitting parameter, representing the prefactor of alloy-disorder scattering
    scal_fac : float
        Scaling factor, by which the function is multiplied

    Returns
    -------
    out : numpy.ndarray
        Numpy array of electron thermal conductivity values
    """

    result: np.ndarray = (
        spb_elecCond_vs_temp_dis(temp_array, sig, para_A, scal_fac)
        * spb_lorNum_vs_temp(temp_array, fermi_energy, band_mass)
        * temp_array
    )
    return result


# Calculates the electrical resistivity of a single band for acoustic-phonon and alloy-disorder
# scattering
def spb_rho_vs_temp_acPh_dis(
    T: np.ndarray, sig: np.ndarray, para_A: float, para_B: float, scal_fac: float = 1.0
) -> np.ndarray:
    """Calculates the resistivity of a single band at various temperatures for a given set of
    acoustic-phonon and alloy-disorder scattering parameters.

    Parameters
    ----------
    T : numpy.ndarray
        Numpy array containing all temperatures
    sig : numpy.ndarray
        'Pristine' conductivity of the band, calculated with mass = mass_sign, K = 1 and beta = 0 at
        the temperatures given by T
    para_A : float
        First fitting parameter, representing the prefactor of acoustic-phonon scattering
    para_B : float
        Second fitting parameter, representing the ratio of the prefactors of acoustic-phonon
        scattering to alloy-disorder scattering
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray
        Numpy array of resistivity values
    """

    result: np.ndarray = scal_fac / (para_A * T / (para_B + T) * sig)
    return result


# Calculates the electrical conductivity of a single band for acoustic-phonon and alloy-disorder
# scattering
def spb_elecCond_vs_temp_acPh_dis(
    temp_array: np.ndarray, sig: np.ndarray, para_A: float, para_B: float, scal_fac: float = 1.0
) -> np.ndarray:
    """Calculates the electrical conductivity of a single band at various temperatures for a given
    set of acoustic-phonon and alloy-disorder scattering parameters.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig : numpy.ndarray
        'Pristine' conductivity of the band, calculated with mass = mass_sign, K = 1 and beta = 0 at
        the temperatures given by temp_array
    para_A : float
        First fitting parameter, representing the prefactor of acoustic-phonon scattering
    para_B : float
        Second fitting parameter, representing the ratio of the prefactors of acoustic-phonon
        scattering to alloy-disorder scattering
    scal_fac : float
        Scaling factor, by which the function is multiplied

    Returns
    -------
    out : numpy.ndarray
        Numpy array of electrical conductivity values
    """

    result: np.ndarray = scal_fac * para_A * temp_array / (para_B + temp_array) * sig
    return result


# Calculates the electron thermal conductivity of a single band for acoustic-phonon and
# alloy-disorder scattering
def spb_thermCond_vs_temp_acPh_dis(
    temp_array: np.ndarray,
    sig: np.ndarray,
    fermi_energy: float,
    band_mass: float,
    para_A: float,
    para_B: float,
    scal_fac: float = 1.0,
) -> np.ndarray:
    """Calculates the electron thermal conductivity of a single band at various temperatures for a
    given set of acoustic-phonon and alloy-disorder scattering parameters.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig : numpy.ndarray
        'Pristine' conductivity of the band, calculated with mass = mass_sign, K = 1 and beta = 0 at
        the temperatures given by temp_array
    para_A : float
        First fitting parameter, representing the prefactor of acoustic-phonon scattering
    para_B : float
        Second fitting parameter, representing the ratio of the prefactors of acoustic-phonon
        scattering to alloy-disorder scattering
    scal_fac : float
        Scaling factor, by which the function is multiplied

    Returns
    -------
    out : numpy.ndarray
        Numpy array of electron thermal conductivity values
    """

    result: np.ndarray = (
        spb_elecCond_vs_temp_acPh_dis(temp_array, sig, para_A, para_B, scal_fac)
        * spb_lorNum_vs_temp(temp_array, fermi_energy, band_mass)
        * temp_array
    )
    return result


# A chemical potential whose carrier density is further than this, relatively, from the density at
# T = 0 is no root, and is left out rather than used.
MAX_DENSITY_MISMATCH = 1e-6


def _conserves_density(
    chemical_potential: np.ndarray, T: np.ndarray, mass_sign: float, fermi_energy: float
) -> np.ndarray:
    """Whether each chemical potential keeps the carrier density at T = 0, or there is none."""
    target = spb_carCon(fermi_energy, mass_sign, 0)
    if not np.isfinite(target) or target <= 0:
        # With no carriers at T = 0 there is no density to keep, as with E_F on the other side.
        return np.ones(T.shape, dtype=bool)
    usable = np.zeros(T.shape, dtype=bool)
    for index, (mu, temp) in enumerate(zip(chemical_potential, T, strict=True)):
        if np.isfinite(mu):
            density = spb_carCon(mu, mass_sign, temp)
            usable[index] = abs(density - target) <= MAX_DENSITY_MISMATCH * target
    return usable


# Calculates the Hall coefficient of a single band
def spb_hall_vs_temp(
    T: np.ndarray,
    fermi_energy: float,
    mass_sign: float,
    para_E: float | list[float],
    scal_fac: float = 1.0,
    *,
    potentials: np.ndarray | None = None,
) -> np.ndarray:
    """Calculates the Hall coefficient of a single band at various temperatures

    Parameters
    ----------
    T : numpy.ndarray
        Numpy array containing all temperatures
    fermi_energy : float
        Position of the Fermi energy with respect to the maximum of the band
    mass_sign : float
        Sign of the band mass; -1 vor valence band, +1 for conduction band
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray
        Numpy array of Hall coefficient values
    """

    factor = 3 * hbar**3 * np.pi**2 / (e * (2 * kB * me) ** (3 / 2)) * 0.5
    temperatures = np.asarray(T, dtype=float)
    if potentials is None:
        potentials = spb_chemPot_vs_temp(temperatures, mass_sign, fermi_energy)
    chemical_potential = potentials
    usable = _conserves_density(chemical_potential, temperatures, mass_sign, fermi_energy)
    result = np.full_like(temperatures, np.nan)
    if usable.any():
        at = temperatures[usable]
        x = mass_sign * chemical_potential[usable] / at
        f0 = _scaled_integrals(0, x)
        prefactor = factor * at**-1.5 * scal_fac / np.asarray(para_E, dtype=float)
        # One inverse Boltzmann factor survives. Apply it after moving the
        # prefactor into log space so an intermediate exp(-eta) cannot overflow.
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            log_magnitude = (
                np.log(np.abs(prefactor))
                + np.log(_scaled_integrals(-0.5, x))
                - 2 * np.log(f0)
                - np.minimum(x, 0.0)
            )
            result[usable] = np.copysign(np.exp(log_magnitude), prefactor)
    return result


"""
DPB
"""


# Calculates the Seebeck coefficient of two bands for the Seebeck-only mode
def dpb_see_vs_temp(
    T: np.ndarray,
    meff: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    scal_fac: float = 1.0,
    *,
    potentials: np.ndarray | None = None,
) -> np.ndarray:
    """Calculates the Seebeck coefficient of two bands at various temperatures for the Seebeck-only
    mode

    Parameters
    ----------
    T : numpy.ndarray
        Numpy array containing all temperatures
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the inverse degeneracies
    gap : numpy.ndarray
        Band gap, i.e. the distance between the minima/maxima of the parabolas
    fermi_energy : float
        Position of the Fermi energy with respect to the maximum of band 1
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray
        Numpy array of Seebeck coefficient values
    """

    x1, x2 = _dpb_reduced_potentials(T, meff, gap, fermi_energy, degen, potentials)
    see1, see2 = _dpb_seebeck_contributions(x1, x2, meff, 1 / abs(meff))
    result: np.ndarray = scal_fac * (see1 + see2)
    return result


# Calculates the Seebeck coefficient of two bands if scattering times of acoustic-phonon and
# alloy-disorder scattering are considered
def dpb_see_vs_temp_double_scatter(
    temp_array: np.ndarray,
    meff: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    para_B: float,
    para_C: float,
    para_D: float,
    scal_fac: float = 1.0,
    *,
    potentials: np.ndarray | None = None,
) -> np.ndarray:
    """Calculates the Seebeck coefficient of two bands at various temperatures for a given set of
    band-structure and scattering parameters.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    meff : float
        First fitting parameter, representing the ratio of the band mass of band 2 to band 1,
        weighted by the degeneracy
    gap : numpy.ndarray
        Second fitting parameter, representing the band gap, i.e. the distance between the
        minima/maxima of the parabolas
    ef : float
        Third fitting parameter, representing the position of the Fermi energy with respect to the
        maximum of band 1
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    para_B : float
        Parameter fitted in 'rho_vs_temp_acPh_dis', representing the ratio of the prefactors of
        acoustic-phonon scattering of band 2 to band 1
    para_C : float
        Parameter fitted in 'rho_vs_temp_acPh_dis', representing the ratio of the prefactors of
        acoustic-phonon scattering to alloy-disorder scattering of band 1
    para_D : float
        Parameter fitted in 'rho_vs_temp_acPh_dis', representing the ratio of the prefactors of
        acoustic-phonon scattering to alloy-disorder scattering of band 2
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray
        Numpy array of Seebeck coefficient values

    See also
    -------
    rho_vs_temp_acPh_dis : Returns an array of resistivity values
    """

    x1, x2 = _dpb_reduced_potentials(temp_array, meff, gap, fermi_energy, degen, potentials)
    see1, see2 = _dpb_seebeck_contributions(
        x1, x2, meff, para_B * (para_C + temp_array) / (para_D + temp_array) / abs(meff)
    )
    result: np.ndarray = scal_fac * (see1 + see2)
    return result


# Calculates the Seebeck coefficient of two bands if scattering times of either acoustic-phonon or
# alloy-disorder scattering are considered
def dpb_see_vs_temp_single_scatter(
    temp_array: np.ndarray,
    meff: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    para_B: float,
    scal_fac: float = 1.0,
    *,
    potentials: np.ndarray | None = None,
) -> np.ndarray:
    """Calculates the Seebeck coefficient of two bands at various temperatures for a given set of
    band-structure scattering parameters.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    meff : float
        First fitting parameter, representing the ratio of the band mass of band 2 to band 1,
        weighted by the degeneracy
    gap : numpy.ndarray
        Second fitting parameter, representing the band gap, i.e. the distance between the
        minima/maxima of the parabolas
    fermi_energy : float
        Third fitting parameter, representing the position of the Fermi energy with respect to the
        maximum of band 1
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    para_B : float
        Parameter fitted in 'dpb_rho_vs_temp_acPh' or 'dpb_rho_vs_temp_dis', representing the ratio
        of the prefactors of either acoustic-phonon or alloy-disorder scattering of band 2 to band 1
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray
        Numpy array of Seebeck coefficient values
    """

    x1, x2 = _dpb_reduced_potentials(temp_array, meff, gap, fermi_energy, degen, potentials)
    see1, see2 = _dpb_seebeck_contributions(x1, x2, meff, para_B / abs(meff))
    result: np.ndarray = scal_fac * (see1 + see2)
    return result


# Calculates the electrical resistivity of two bands for acoustic-phonon scattering
def dpb_rho_vs_temp_acPh(
    T: np.ndarray,
    f0_1: np.ndarray,
    f0_2: np.ndarray,
    para_A: float,
    para_B: float,
    meff: float,
    scal_fac: float = 1.0,
) -> np.ndarray:
    """Calculates the resistivity of two bands at various temperatures for a given set of scattering
    parameters.

    Parameters
    ----------
    T : numpy.ndarray
        Numpy array containing all temperatures
    sig1 : numpy.ndarray
        'Pristine' conductivity of band 1, calculated with mass = -1, K = 1 and beta = 0 at the
        temperatures given by T
    sig2 : numpy.ndarray
        'Pristine' conductivity of band 2, calculated with mass = numpy.sign(meff), K = 1 and beta =
        0 at the temperatures given by T
    para_A : float
        First fitting parameter, representing the prefactor of acoustic-phonon scattering of band 1
    para_B : float
        Second fitting parameter, representing the ratio of the prefactors of acoustic-phonon
        scattering of band 2 to band 1
    meff : float
        Parameter, representing the ratio of the band mass of band 2 to band 1, weighted by the
        degeneracy
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray
        Numpy array of resistivity values
    """

    return scal_fac / (para_A * (f0_1 + 1 / abs(meff) * para_B * f0_2))


# Calculates the electrical resistivity of two bands for alloy-disorder scattering
def dpb_rho_vs_temp_dis(
    T: np.ndarray,
    f0_1: np.ndarray,
    f0_2: np.ndarray,
    para_A: float,
    para_B: float,
    meff: float,
    scal_fac: float = 1.0,
) -> np.ndarray:
    """Calculates the resistivity of two bands at various temperatures for a given set of
    alloy-disorder scattering parameters.

    Parameters
    ----------
    T : numpy.ndarray
        Numpy array containing all temperatures
    sig1 : numpy.ndarray
        'Pristine' conductivity of band 1, calculated with mass = -1, K = 1 and beta = 0 at the
        temperatures given by T
    sig2 : numpy.ndarray
        'Pristine' conductivity of band 2, calculated with mass = numpy.sign(meff), K = 1 and beta =
        0 at the temperatures given by T
    para_A : float
        First fitting parameter, representing the prefactor of alloy-disorder scattering of band 1
    para_B : float
        Second fitting parameter, representing the ratio of the prefactors of alloy-disorder
        scattering of band 2 to band 1
    meff : float
        Parameter, representing the ratio of the band mass of band 2 to band 1, weighted by the
        degeneracy
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray
        Numpy array of resistivity values
    """

    return scal_fac / (para_A * T * (f0_1 + 1 / abs(meff) * para_B * f0_2))


# Calculates the electrical resistivity of two bands for acoustic-phonon and alloy-disorder
# scattering
def dpb_rho_vs_temp_acPh_dis(
    T: np.ndarray,
    f0_1: np.ndarray,
    f0_2: np.ndarray,
    para_A: float,
    para_B: float,
    para_C: float,
    para_D: float,
    meff: float,
    scal_fac: float = 1.0,
) -> np.ndarray:
    """Calculates the resistivity of two bands at various temperatures for a given set of scattering
    parameters.

    Parameters
    ----------
    T : numpy.ndarray
        Numpy array containing all temperatures
    sig1 : numpy.ndarray
        'Pristine' conductivity of band 1, calculated with mass = -1, K = 1 and beta = 0 at the
        temperatures given by T
    sig2 : numpy.ndarray
        'Pristine' conductivity of band 2, calculated with mass = numpy.sign(meff), K = 1 and beta =
        0 at the temperatures given by T
    para_A : float
        First fitting parameter, representing the prefactor of acoustic-phonon scattering of band 1
    para_B : float
        Second fitting parameter, representing the ratio of the prefactors of acoustic-phonon
        scattering of band 2 to band 1
    para_C : float
        Third fitting parameter, representing the ratio of the prefactors of acoustic-phonon
        scattering to alloy-disorder scattering of band 1
    para_D : float
        Fourth fitting parameter, representing the ratio of the prefactors of acoustic-phonon
        scattering to alloy-disorder scattering of band 2
    meff : float
        Parameter, representing the ratio of the band mass of band 2 to band 1, weighted by the
        degeneracy
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray
        Numpy array of resistivity values
    """

    return scal_fac / (
        para_A * T * (f0_1 / (para_C + T) + 1 / abs(meff) * para_B * f0_2 / (para_D + T))
    )


def _bipolar_conductivity(sig1: np.ndarray, sig2: np.ndarray) -> np.ndarray:
    # sigma1*sigma2/(sigma1+sigma2), without multiplying two dilute band
    # conductivities. If both are zero, their bipolar conductivity is zero.
    total = sig1 + sig2
    fraction = np.divide(
        np.maximum(sig1, sig2), total, out=np.zeros_like(total), where=(sig1 != 0) | (sig2 != 0)
    )
    result: np.ndarray = np.minimum(sig1, sig2) * fraction
    return result


# Calculates the electron thermal conductivity of two bands for acoustic-phonon scattering
def dpb_thermCond_vs_temp_acPh(
    temp_array: np.ndarray,
    f0_1: np.ndarray,
    f0_2: np.ndarray,
    para_A: float,
    para_B: float,
    meff: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    scal_fac: float = 1.0,
) -> np.ndarray:
    """Calculates the electron thermal conductivity of two bands at various temperatures for a given
    set of scattering parameters.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig1 : numpy.ndarray
        'Pristine' conductivity of band 1, calculated with mass = -1, K = 1 and beta = 0 at the
        temperatures given by temp_array
    sig2 : numpy.ndarray
        'Pristine' conductivity of band 2, calculated with mass = numpy.sign(meff), K = 1 and beta =
        0 at the temperatures given by temp_array
    para_A : float
        Prefactor of alloy-disorder scattering of band 1
    para_B : float
        Ratio of the prefactors of alloy-disorder scattering of band 2 to band 1
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the inverse degeneracies
    gap : numpy.ndarray
        Band gap, i.e. the distance between the minima/maxima of the parabolas
    fermi_energy : float
        Position of the Fermi energy with respect to the maximum of band 1
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    scal_fac : float
        Scaling factor, by which the function is multiplied

    Returns
    -------
    out : numpy.ndarray
        Numpy array of electron thermal conductivity values
    """

    sig1, sig2 = dpb_ind_elecCond_vs_temp_acPh(
        temp_array, f0_1, f0_2, para_A, para_B, meff, scal_fac=1.0
    )
    see1, see2 = dpb_ind_see_vs_temp(temp_array, meff, gap, fermi_energy, degen, scal_fac=1.0)
    lorNum_1, lorNum_2 = dpb_lorNum_vs_temp(temp_array, meff, gap, fermi_energy, degen)

    result: np.ndarray = temp_array * (
        scal_fac * (lorNum_1 * sig1 + lorNum_2 * sig2)
        + _bipolar_conductivity(sig1, sig2) * (see1 - see2) ** 2
    )
    return result


# Calculates the electron thermal conductivity of two bands for alloy-disorder scattering
def dpb_thermCond_vs_temp_dis(
    temp_array: np.ndarray,
    f0_1: np.ndarray,
    f0_2: np.ndarray,
    para_A: float,
    para_B: float,
    meff: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    scal_fac: float = 1.0,
) -> np.ndarray:
    """Calculates the electron thermal conductivity of two bands at various temperatures for a given
    set of scattering parameters.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig1 : numpy.ndarray
        'Pristine' conductivity of band 1, calculated with mass = -1, K = 1 and beta = 0 at the
        temperatures given by temp_array
    sig2 : numpy.ndarray
        'Pristine' conductivity of band 2, calculated with mass = numpy.sign(meff), K = 1 and beta =
        0 at the temperatures given by temp_array
    para_A : float
        Prefactor of alloy-disorder scattering of band 1
    para_B : float
        Ratio of the prefactors of alloy-disorder scattering of band 2 to band 1
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the inverse degeneracies
    gap : numpy.ndarray
        Band gap, i.e. the distance between the minima/maxima of the parabolas
    fermi_energy : float
        Position of the Fermi energy with respect to the maximum of band 1
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    scal_fac : float
        Scaling factor, by which the function is multiplied

    Returns
    -------
    out : numpy.ndarray
        Numpy array of electron thermal conductivity values
    """

    sig1, sig2 = dpb_ind_elecCond_vs_temp_dis(
        temp_array, f0_1, f0_2, para_A, para_B, meff, scal_fac=1.0
    )
    see1, see2 = dpb_ind_see_vs_temp(temp_array, meff, gap, fermi_energy, degen, scal_fac=1.0)
    lorNum_1, lorNum_2 = dpb_lorNum_vs_temp(temp_array, meff, gap, fermi_energy, degen)

    result: np.ndarray = temp_array * (
        scal_fac * (lorNum_1 * sig1 + lorNum_2 * sig2)
        + _bipolar_conductivity(sig1, sig2) * (see1 - see2) ** 2
    )
    return result


# Calculates the electron thermal conductivity of two bands for acoustic-phonon and alloy-disorder
# scattering
def dpb_thermCond_vs_temp_acPh_dis(
    temp_array: np.ndarray,
    f0_1: np.ndarray,
    f0_2: np.ndarray,
    para_A: float,
    para_B: float,
    para_C: float,
    para_D: float,
    meff: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    scal_fac: float = 1.0,
) -> np.ndarray:
    """Calculates the electron thermal conductivity of two bands at various temperatures for a given
    set of scattering parameters.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig1 : numpy.ndarray
        'Pristine' conductivity of band 1, calculated with mass = -1, K = 1 and beta = 0 at the
        temperatures given by temp_array
    sig2 : numpy.ndarray
        'Pristine' conductivity of band 2, calculated with mass = numpy.sign(meff), K = 1 and beta =
        0 at the temperatures given by temp_array
    para_A : float
        Prefactor of alloy-disorder scattering of band 1
    para_B : float
        Ratio of the prefactors of alloy-disorder scattering of band 2 to band 1
    para_C : float
        Ratio of the prefactors of acoustic-phonon scattering to alloy-disorder scattering of band 1
    para_D : float
        Ratio of the prefactors of acoustic-phonon scattering to alloy-disorder scattering of band 2
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the inverse degeneracies
    gap : numpy.ndarray
        Band gap, i.e. the distance between the minima/maxima of the parabolas
    fermi_energy : float
        Position of the Fermi energy with respect to the maximum of band 1
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    scal_fac : float
        Scaling factor, by which the function is multiplied

    Returns
    -------
    out : numpy.ndarray
        Numpy array of electron thermal conductivity values
    """

    sig1, sig2 = dpb_ind_elecCond_vs_temp_acPh_dis(
        temp_array, f0_1, f0_2, para_A, para_B, para_C, para_D, meff, scal_fac=1.0
    )
    see1, see2 = dpb_ind_see_vs_temp(temp_array, meff, gap, fermi_energy, degen, scal_fac=1.0)
    lorNum_1, lorNum_2 = dpb_lorNum_vs_temp(temp_array, meff, gap, fermi_energy, degen)

    result: np.ndarray = temp_array * (
        scal_fac * (lorNum_1 * sig1 + lorNum_2 * sig2)
        + _bipolar_conductivity(sig1, sig2) * (see1 - see2) ** 2
    )
    return result


# Calculates the Hall coefficient of two bands for acoustic-phonon scattering
def dpb_hall_vs_temp_acPh(
    T: np.ndarray,
    rho: np.ndarray,
    f_m05_1: np.ndarray,
    f_m05_2: np.ndarray,
    meff: float,
    degen: float,
    para_A: float,
    para_B: float,
    para_E: float | list[float],
    scal_fac: float = 1.0,
    *,
    band_1_degeneracy: float = 1.0,
) -> np.ndarray:
    """
    Calculates the Hall coefficient of two bands at various temperatures for a given set of
    band-structure, scattering and mass parameters.

    Parameters
    ----------
    T : numpy.ndarray
        Temperature
    rho : numpy.ndarray
        Total resistivity at the temperatures given by T
    f_m05_1 : numpy.ndarray
        Fermi integral of -0.5th order of band 1 at the temperatures given by T
    f_m05_2 : numpy.ndarray
        Fermi integral of -0.5th order of band 2 at the temperatures given by T
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the degeneracy
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    para_A : float
        Scattering-related parameter, proportional to the prefactor of acoustic-phonon scattering of
        band 1
    para_B : float
        Scattering-related parameter, proportional to the ratio of the prefactors of acoustic-phonon
        scattering of band 2 to band 1
    para_E : float
        Fitting parameter, proportional to the mass of band 1
    scal_fac : float
        Scaling factor, by which the function is multiplied for improved fitting convergence
    band_1_degeneracy : float
        Absolute valley multiplicity of band 1. The relative valley weight is in degen.
    Returns
    -------
    out : numpy.ndarray
        Numpy array of Hall coefficient values
    """

    factor = 3 * hbar**3 * np.pi**2 / (e * (2 * kB * me) ** (3 / 2)) * 0.5
    result: np.ndarray = (
        factor
        * T ** (-1.5)
        * scal_fac
        * rho
        * para_A**2
        / para_E
        / band_1_degeneracy
        * (
            f_m05_1
            - np.sign(meff)
            / degen ** (5 / 2)
            / (np.abs(meff)) ** (3 / 2)
            * (para_B / meff) ** 2
            * f_m05_2
        )
        * rho
    )
    return result


# Calculates the Hall coefficient of two bands for alloy-disorder scattering
def dpb_hall_vs_temp_dis(
    T: np.ndarray,
    rho: np.ndarray,
    f_m05_1: np.ndarray,
    f_m05_2: np.ndarray,
    meff: float,
    degen: float,
    para_A: float,
    para_B: float,
    para_E: float | list[float],
    scal_fac: float = 1.0,
    *,
    band_1_degeneracy: float = 1.0,
) -> np.ndarray:
    """
    Calculates the Hall coefficient of two bands at various temperatures for a given set of
    band-structure, scattering and mass parameters.

    Parameters
    ----------
    T : numpy.ndarray
        Temperature
    rho : numpy.ndarray
        Total resistivity at the temperatures given by T
    f_m05_1 : numpy.ndarray
        Fermi integral of -0.5th order of band 1 at the temperatures given by T
    f_m05_2 : numpy.ndarray
        Fermi integral of -0.5th order of band 2 at the temperatures given by T
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the degeneracy
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    para_A : float
        Scattering-related parameter, proportional to the prefactor of acoustic-phonon scattering of
        band 1
    para_B : float
        Scattering-related parameter, proportional to the ratio of the prefactors of acoustic-phonon
        scattering of band 2 to band 1
    para_E : float
        Free parameter, proportional to the mass of band 1
    scal_fac : float
        Scaling factor, by which the function is multiplied for improved fitting convergence
    band_1_degeneracy : float
        Absolute valley multiplicity of band 1. The relative valley weight is in degen.
    Returns
    -------
    out : numpy.ndarray
        Numpy array of Hall coefficient values
    """

    factor = 3 * hbar**3 * np.pi**2 / (e * (2 * kB * me) ** (3 / 2)) * 0.5
    result: np.ndarray = (
        factor
        * T ** (0.5)
        * scal_fac
        * rho
        * para_A**2
        / para_E
        / band_1_degeneracy
        * (
            f_m05_1
            - np.sign(meff)
            / degen ** (5 / 2)
            / (np.abs(meff)) ** (3 / 2)
            * (para_B / meff) ** 2
            * f_m05_2
        )
        * rho
    )
    return result


# Calculates the Hall coefficient of two bands for acoustic-phonon and alloy-disorder scattering
def dpb_hall_vs_temp_acPh_dis(
    T: np.ndarray,
    rho: np.ndarray,
    f_m05_1: np.ndarray,
    f_m05_2: np.ndarray,
    meff: float,
    degen: float,
    para_A: float,
    para_B: float,
    para_C: float,
    para_D: float,
    para_E: float | list[float],
    scal_fac: float = 1.0,
    *,
    band_1_degeneracy: float = 1.0,
) -> np.ndarray:
    """
    Calculates the Hall coefficient of two bands at various temperatures for a given set of
    band-structure, scattering and mass parameters.

    Parameters
    ----------
    T : numpy.ndarray
        Temperature
    rho : numpy.ndarray
        Total resistivity at the temperatures given by T
    f_m05_1 : numpy.ndarray
        Fermi integral of -0.5th order of band 1 at the temperatures given by T
    f_m05_2 : numpy.ndarray
        Fermi integral of -0.5th order of band 2 at the temperatures given by T
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the degeneracy
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    para_A : float
        Scattering-related parameter, proportional to the prefactor of acoustic-phonon scattering of
        band 1
    para_B : float
        Scattering-related parameter, proportional to the ratio of the prefactors of acoustic-phonon
        scattering of band 2 to band 1
    para_C : float
        Scattering-related parameter, proportional to the ratio of the prefactors of acoustic-phonon
        scattering to alloy-disorder scattering of band 1
    para_D : float
        Scattering-related parameter, proportional to the ratio of the prefactors of acoustic-phonon
        scattering to alloy-disorder scattering of band 2
    para_E : float
        Fitting parameter, proportional to the mass of band 1
    scal_fac : float
        Scaling factor, by which the function is multiplied for improved fitting convergence
    band_1_degeneracy : float
        Absolute valley multiplicity of band 1. The relative valley weight is in degen.
    Returns
    -------
    out : numpy.ndarray
        Numpy array of Hall coefficient values
    """

    factor = 3 * hbar**3 * np.pi**2 / (e * (2 * kB * me) ** (3 / 2)) * 0.5
    result: np.ndarray = (
        factor
        * T ** (0.5)
        * scal_fac
        * rho
        * para_A**2
        / para_E
        / band_1_degeneracy
        * (
            (1 / (para_C + T)) ** 2 * f_m05_1
            - np.sign(meff)
            / degen ** (5 / 2)
            / (np.abs(meff)) ** (3 / 2)
            * (para_B / meff / (para_D + T)) ** 2
            * f_m05_2
        )
        * rho
    )
    return result


"""
Individual contributions
"""


# Calculates the individual Seebeck coefficients of two bands
def dpb_ind_see_vs_temp(
    temp_array: np.ndarray,
    meff: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    scal_fac: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculates the individual Seebeck coefficients of two bands at various temperatures for the
    Seebeck-only mode

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the inverse degeneracies
    gap : numpy.ndarray
        Band gap, i.e. the distance between the minima/maxima of the parabolas
    fermi_energy : float
        Position of the Fermi energy with respect to the maximum of band 1
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    scal_fac : float
        Scaling factor, by which both functions are multiplied

    Returns
    -------
    out : numpy.ndarray, numpy.ndarray
        Tuple of numpy array of individual Seebeck coefficients
    """

    x1, x2 = _dpb_reduced_potentials(temp_array, meff, gap, fermi_energy, degen)
    return scal_fac * _band_seebeck(x1, -1), scal_fac * _band_seebeck(x2, float(np.sign(meff)))


# Calculates the individual contributions to the Seebeck coefficient of two bands for the
# Seebeck-only mode
def dpb_indCont_see_vs_temp(
    temp_array: np.ndarray,
    meff: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    scal_fac: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculates the individual contributions to the Seebeck coefficient of two bands at various
    temperatures for the Seebeck-only mode

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the inverse degeneracies
    gap : numpy.ndarray
        Band gap, i.e. the distance between the minima/maxima of the parabolas
    fermi_energy : float
        Position of the Fermi energy with respect to the maximum of band 1
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    scal_fac : float
        Scaling factor, by which both functions are multiplied

    Returns
    -------
    out : numpy.ndarray, numpy.ndarray
        Tuple of numpy array of individual Seebeck coefficient contributions
    """

    x1, x2 = _dpb_reduced_potentials(temp_array, meff, gap, fermi_energy, degen)
    see1, see2 = _dpb_seebeck_contributions(x1, x2, meff, 1 / abs(meff))
    return scal_fac * see1, scal_fac * see2


# Calculates the individual contributions to the Seebeck coefficient of two bands if scattering
# times of acoustic-phonon and alloy-disorder scattering are considered
def dpb_indCont_see_vs_temp_double_scatter(
    temp_array: np.ndarray,
    meff: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    para_B: float,
    para_C: float,
    para_D: float,
    scal_fac: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculates the individual contributions to the Seebeck coefficient of two bands at various
    temperatures for a given set of band-structure and scattering parameters.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the degeneracy
    gap : numpy.ndarray
        Band gap, i.e. the distance between the minima/maxima of the parabolas
    fermi_energy : float
        Position of the Fermi energy with respect to the maximum of band 1
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    para_B : float
        Ratio of the prefactors of acoustic-phonon scattering of band 2 to band 1
    para_C : float
        Ratio of the prefactors of acoustic-phonon scattering to alloy-disorder scattering of band 1
    para_D : float
        Ratio of the prefactors of acoustic-phonon scattering to alloy-disorder scattering of band 2
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray, numpy.ndarray
        Tuple of numpy array of individual Seebeck coefficient contributions
    """

    x1, x2 = _dpb_reduced_potentials(temp_array, meff, gap, fermi_energy, degen)
    see1, see2 = _dpb_seebeck_contributions(
        x1, x2, meff, para_B * (para_C + temp_array) / (para_D + temp_array) / abs(meff)
    )
    return scal_fac * see1, scal_fac * see2


# Calculates the individual contributions to the Seebeck coefficient of two bands if scattering
# times of either acoustic-phonon or alloy-disorder scattering are considered
def dpb_indCont_see_vs_temp_single_scatter(
    temp_array: np.ndarray,
    meff: float,
    gap: float,
    fermi_energy: float,
    degen: float,
    para_B: float,
    scal_fac: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculates the individual contributions to the Seebeck coefficient of two bands at various
    temperatures for a given set of band-structure scattering parameters.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the degeneracy
    gap : numpy.ndarray
        Band gap, i.e. the distance between the minima/maxima of the parabolas
    fermi_energy : float
        Position of the Fermi energy with respect to the maximum of band 1
    degen : float
        Ratio of the degeneracy of band 2 to band 1
    para_B : float
        Parameter fitted in 'dpb_rho_vs_temp_acPh' or 'dpb_rho_vs_temp_dis', representing the ratio
        of the prefactors of either acoustic-phonon or alloy-disorder scattering of band 2 to band 1
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray, numpy.ndarray
        Tuple of numpy array of individual Seebeck coefficient contributions
    """

    x1, x2 = _dpb_reduced_potentials(temp_array, meff, gap, fermi_energy, degen)
    see1, see2 = _dpb_seebeck_contributions(x1, x2, meff, para_B / abs(meff))
    return scal_fac * see1, scal_fac * see2


# Calculates the individual electrical conductivities of two bands for acoustic-phonon scattering
def dpb_ind_elecCond_vs_temp_acPh(
    temp_array: np.ndarray,
    f0_1: np.ndarray,
    f0_2: np.ndarray,
    para_A: float,
    para_B: float,
    meff: float,
    scal_fac: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculates the individual electrical conductivities of two bands at various temperatures for
    a given set of scattering parameters.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig1 : numpy.ndarray
        'Pristine' conductivity of band 1, calculated with mass = -1, K = 1 and beta = 0 at the
        temperatures given by temp_array
    sig2 : numpy.ndarray
        'Pristine' conductivity of band 2, calculated with mass = numpy.sign(meff), K = 1 and beta =
        0 at the temperatures given by temp_array
    para_A : float
        Prefactor of acoustic-phonon scattering of band 1
    para_B : float
        Ratio of the prefactors of acoustic-phonon scattering of band 2 to band 1
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the degeneracy
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray, numpy.ndarray
        Tuple of numpy arrays of individual electrical conductivities
    """

    sig1 = scal_fac * para_A * f0_1
    sig2 = scal_fac * para_A * 1 / abs(meff) * para_B * f0_2

    return sig1, sig2


# Calculates the individual electrical conductivities of two bands for alloy-disorder scattering
def dpb_ind_elecCond_vs_temp_dis(
    temp_array: np.ndarray,
    f0_1: np.ndarray,
    f0_2: np.ndarray,
    para_A: float,
    para_B: float,
    meff: float,
    scal_fac: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculates the individual electrical conductivities of two bands at various temperatures for
    a given set of alloy-disorder scattering parameters.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig1 : numpy.ndarray
        'Pristine' conductivity of band 1, calculated with mass = -1, K = 1 and beta = 0 at the
        temperatures given by temp_array
    sig2 : numpy.ndarray
        'Pristine' conductivity of band 2, calculated with mass = numpy.sign(meff), K = 1 and beta =
        0 at the temperatures given by temp_array
    para_A : float
        Prefactor of alloy-disorder scattering of band 1
    para_B : float
        Ratio of the prefactors of alloy-disorder scattering of band 2 to band 1
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the degeneracy
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray, numpy.ndarray
        Tuple of numpy arrays of individual electrical conductivities
    """

    sig1 = scal_fac * para_A * temp_array * f0_1
    sig2 = scal_fac * para_A * temp_array * 1 / abs(meff) * para_B * f0_2

    return sig1, sig2


# Calculates the individual electrical conductivities of two bands for acoustic-phonon and
# alloy-disorder scattering
def dpb_ind_elecCond_vs_temp_acPh_dis(
    temp_array: np.ndarray,
    f0_1: np.ndarray,
    f0_2: np.ndarray,
    para_A: float,
    para_B: float,
    para_C: float,
    para_D: float,
    meff: float,
    scal_fac: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculates the individual electrical conductivities of two bands at various temperatures for
    a given set of scattering parameters.

    Parameters
    ----------
    temp_array : numpy.ndarray
        Numpy array containing all temperatures
    sig1 : numpy.ndarray
        'Pristine' conductivity of band 1, calculated with mass = -1, K = 1 and beta = 0 at the
        temperatures given by temp_array
    sig2 : numpy.ndarray
        'Pristine' conductivity of band 2, calculated with mass = numpy.sign(meff), K = 1 and beta =
        0 at the temperatures given by temp_array
    para_A : float
        Prefactor of acoustic-phonon scattering of band 1
    para_B : float
        Ratio of the prefactors of acoustic-phonon scattering of band 2 to band 1
    para_C : float
        Ratio of the prefactors of acoustic-phonon scattering to alloy-disorder scattering of band 1
    para_D : float
        Ratio of the prefactors of acoustic-phonon scattering to alloy-disorder scattering of band 2
    meff : float
        Ratio of the band mass of band 2 to band 1, weighted by the degeneracy
    scal_fac : float
        Scaling factor, by which the function is multiplied for improvied fitting convergence

    Returns
    -------
    out : numpy.ndarray, numpy.ndarray
        Tuple of numpy arrays of individual electrical conductivities
    """

    sig1 = scal_fac * para_A * temp_array * f0_1 / (para_C + temp_array)
    sig2 = scal_fac * para_A * temp_array * 1 / abs(meff) * para_B * f0_2 / (para_D + temp_array)

    return sig1, sig2


# Calculates the individual temperature-dependent charge carrier concentrations of two bands
def dpb_ind_carCon_vs_temp(
    temp_array: np.ndarray, fermi_energy: float, meff: float, gap: float, degen: float
) -> tuple[np.ndarray, np.ndarray]:

    chemPot_array = dpb_chemPot_vs_temp(temp_array, gap, meff, fermi_energy, degen)
    charCon1 = np.zeros(shape=len(temp_array))
    charCon2 = np.zeros(shape=len(temp_array))

    for i, temp in enumerate(temp_array):
        charCon1[i] = spb_carCon(chemPot_array[i], -1, temp) * (-1)
        charCon2[i] = spb_carCon(chemPot_array[i] - gap, meff * degen ** (5 / 3), temp) * np.sign(
            meff
        )
    return charCon1, charCon2


"""
#################################################
Temporary helper functions
#################################################
"""


def parabolic_band(k: float, mass: float, energy: float) -> float:
    """Return E/k_B in K for k in nm^-1, signed mass in m_e, and edge energy in K."""
    if mass == 0.0 or not np.isfinite(mass):
        return float("nan")
    curvature = (hbar * 1e9) ** 2 / (2 * me * BOLTZMANN_EV_PER_K * e)
    return energy + curvature * k**2 / mass
